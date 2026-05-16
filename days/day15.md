# Day 15 — App Security

**태그**: Keychain · Biometric · Certificate Pinning · Jailbreak Detection · ATS

---

## 📝 핵심 정리


### 1. Keychain with Biometric 인증

_아이콘: `blue`_


### Keychain이란?

iOS에서 민감한 데이터(비밀번호, 토큰, 인증서)를 **암호화하여 안전하게 저장**하는 시스템 서비스입니다. 앱이 삭제되어도 데이터가 유지될 수 있습니다.

### Keychain + Face ID/Touch ID

```swift
import Security
import LocalAuthentication

class KeychainManager {
    
    // Biometric 보호된 항목 저장
    func saveWithBiometric(token: String, account: String) throws {
        let context = LAContext()
        context.touchIDAuthenticationAllowableReuseDuration = 10
        
        // Access Control: 생체인증 필요
        guard let accessControl = SecAccessControlCreateWithFlags(
            nil,
            kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly,
            .biometryCurrentSet,  // 현재 등록된 생체정보로만
            nil
        ) else {
            throw KeychainError.accessControlFailed
        }
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: account,
            kSecValueData as String: token.data(using: .utf8)!,
            kSecAttrAccessControl as String: accessControl,
            kSecUseAuthenticationContext as String: context
        ]
        
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.saveFailed(status)
        }
    }
    
    // Biometric 인증 후 읽기
    func readWithBiometric(account: String) throws -> String {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecUseOperationPrompt as String: "인증이 필요합니다"
        ]
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        guard status == errSecSuccess,
              let data = result as? Data,
              let token = String(data: data, encoding: .utf8) else {
            throw KeychainError.readFailed(status)
        }
        return token
    }
}
```

### kSecAttrAccessible 옵션

| 옵션 | 접근 가능 시점 | 용도 |
|---|---|---|
| WhenUnlocked | 잠금 해제 시 | 일반 토큰 |
| AfterFirstUnlock | 첫 잠금해제 후 항상 | 백그라운드 작업용 |
| WhenPasscodeSetThisDeviceOnly | 패스코드 설정 + 잠금해제 | 최고 보안 |

> 💡 **💡 면접 포인트:** "Keychain은 Secure Enclave와 연동되어 하드웨어 수준 암호화를 제공합니다. biometryCurrentSet 플래그를 사용하면 생체정보가 변경(새 지문 등록)되면 기존 항목에 접근할 수 없어 보안이 강화됩니다. ThisDeviceOnly 옵션으로 iCloud 백업에서 제외할 수 있습니다."


### 2. Certificate Pinning 구현

_아이콘: `green`_


### Certificate Pinning이란?

앱이 서버와 통신할 때 **미리 알고 있는 인증서(또는 공개키)만 신뢰**하도록 하는 보안 기법입니다. 중간자 공격(MITM)을 방지합니다.

### URLSession으로 구현

```swift
class PinnedSessionDelegate: NSObject, URLSessionDelegate {
    
    // 서버의 공개키 해시 (SHA-256)
    private let pinnedPublicKeyHashes: Set<String> = [
        "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",  // 현재 인증서
        "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC="   // 백업 인증서
    ]
    
    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // 인증서 체인 검증
        let policies = [SecPolicyCreateSSL(true, challenge.protectionSpace.host as CFString)]
        SecTrustSetPolicies(serverTrust, policies as CFTypeRef)
        
        var error: CFError?
        guard SecTrustEvaluateWithError(serverTrust, &error) else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // 공개키 해시 비교
        guard let serverCert = SecTrustGetCertificateAtIndex(serverTrust, 0),
              let serverPublicKey = SecCertificateCopyKey(serverCert),
              let serverPublicKeyData = SecKeyCopyExternalRepresentation(serverPublicKey, nil) as Data? else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        let hash = sha256(data: serverPublicKeyData)
        let hashBase64 = hash.base64EncodedString()
        
        if pinnedPublicKeyHashes.contains(hashBase64) {
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }
}
```

### Pinning 전략

- **Certificate Pinning**: 인증서 전체를 비교. 인증서 갱신 시 앱 업데이트 필요

- **Public Key Pinning**: 공개키만 비교. 인증서 갱신해도 키가 같으면 OK (권장)

- **백업 핀**: 최소 2개 이상의 핀을 포함하여 인증서 교체 시 대응

> 💡 **💡 면접 답변:** "Public Key Pinning을 사용하여 인증서 갱신에도 유연하게 대응합니다. 반드시 백업 핀을 포함하고, 핀 불일치 시 앱이 완전히 동작 불능이 되지 않도록 fallback 전략(강제 업데이트 안내 등)을 마련합니다."


### 3. Jailbreak 탐지와 ATS

_아이콘: `purple`_


### Jailbreak 탐지 방법

```swift
class SecurityChecker {
    
    static func isJailbroken() -> Bool {
        #if targetEnvironment(simulator)
        return false
        #else
        // 1. 의심 파일 존재 확인
        let suspiciousPaths = [
            "/Applications/Cydia.app",
            "/Library/MobileSubstrate/MobileSubstrate.dylib",
            "/bin/bash",
            "/usr/sbin/sshd",
            "/etc/apt",
            "/private/var/lib/apt/"
        ]
        for path in suspiciousPaths {
            if FileManager.default.fileExists(atPath: path) {
                return true
            }
        }
        
        // 2. 샌드박스 밖 쓰기 시도
        let testPath = "/private/jailbreak_test"
        do {
            try "test".write(toFile: testPath, atomically: true, encoding: .utf8)
            try FileManager.default.removeItem(atPath: testPath)
            return true  // 쓰기 성공 = 탈옥
        } catch {
            // 쓰기 실패 = 정상
        }
        
        // 3. URL Scheme 확인
        if let url = URL(string: "cydia://package/com.test"),
           UIApplication.shared.canOpenURL(url) {
            return true
        }
        
        // 4. dyld 이미지 검사 (DYLD_INSERT_LIBRARIES)
        let count = _dyld_image_count()
        for i in 0..<count {
            if let name = _dyld_get_image_name(i) {
                let imageName = String(cString: name)
                if imageName.contains("MobileSubstrate") ||
                   imageName.contains("cycript") {
                    return true
                }
            }
        }
        
        return false
        #endif
    }
}
```

### App Transport Security (ATS)

```swift
// Info.plist 설정
// 기본: 모든 HTTP 차단, HTTPS만 허용

// 특정 도메인 예외 (최소한으로)
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSExceptionDomains</key>
    <dict>
        <key>legacy-api.example.com</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <true/>
            <key>NSExceptionMinimumTLSVersion</key>
            <string>TLSv1.2</string>
        </dict>
    </dict>
</dict>
```

### ATS 요구사항

- TLS 1.2 이상

- Forward Secrecy 지원 암호화 스위트

- SHA-256 이상의 인증서 서명

- 2048비트 이상 RSA 키 또는 256비트 이상 ECC 키

> 💡 **💡 면접 답변:** "Jailbreak 탐지는 다층 방어로 구현합니다. 파일 존재 확인, 샌드박스 무결성, dyld 이미지 검사를 조합합니다. 단, 탈옥 탐지는 우회 가능하므로 서버 측 검증과 함께 사용해야 합니다. ATS는 기본적으로 HTTPS를 강제하며, 예외는 최소한으로 설정하고 App Review에서 사유를 설명해야 합니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. Keychain과 UserDefaults의 차이는? `[기본 / 빈출]`

**보안 수준이 완전히 다릅니다.**

• **UserDefaults**: plist 파일로 저장, 암호화 없음, 탈옥 시 쉽게 읽힘. 설정값, 플래그 등 비민감 데이터용
• **Keychain**: Secure Enclave 연동 암호화, 앱 삭제 후에도 유지 가능, 생체인증 연동 가능. 토큰, 비밀번호, 인증서 등 민감 데이터용

절대 UserDefaults에 저장하면 안 되는 것: 액세스 토큰, 비밀번호, API 키, 개인정보


### Q2. Certificate Pinning의 위험성은? `[심화 / 빈출]`

**인증서 만료/교체 시 앱이 완전히 동작 불능이 될 수 있습니다.**

대응 전략:
1. **백업 핀 포함**: 최소 2개 이상의 공개키 핀
2. **Public Key Pinning**: 인증서가 아닌 공개키를 핀 (갱신에 유연)
3. **강제 업데이트 메커니즘**: 핀 불일치 시 앱 업데이트 유도
4. **Remote Config**: 서버에서 핀 목록을 업데이트할 수 있는 구조
5. **만료 모니터링**: 인증서 만료 30일 전 알림


### Q3. iOS 앱에서 데이터 암호화 계층은? `[심화]`

**4단계 보호 계층:**

1. **하드웨어 (Secure Enclave)**: 키 생성/저장, 생체인증 처리
2. **파일 시스템 (Data Protection)**: NSFileProtectionComplete 등 파일 단위 암호화
3. **Keychain**: 민감 데이터 항목별 암호화 + 접근 제어
4. **앱 레벨**: CryptoKit으로 추가 암호화 (E2E 등)

각 계층이 독립적으로 동작하여 하나가 뚫려도 다른 계층이 보호합니다.


### Q4. Jailbreak 탐지를 우회하는 방법과 대응은? `[심화 / 빈출]`

**우회 방법:** Frida, Liberty Lite 등의 도구로 탐지 함수를 후킹하여 항상 false 반환하도록 변조

**대응 전략:**
1. **다층 탐지**: 여러 방법을 조합하여 하나만 우회해도 다른 것이 감지
2. **코드 난독화**: 탐지 로직을 찾기 어렵게
3. **서버 측 검증**: DeviceCheck API, 앱 무결성 검증
4. **런타임 무결성**: 함수 포인터 변조 감지

궁극적으로 클라이언트 탐지는 우회 가능하므로, 서버에서 민감 로직을 처리하는 것이 근본 해결책입니다.


---


## ✏️ 퀴즈


### 문제 1

Keychain에서 kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly의 의미는?


   **A.** 패스코드 없이도 접근 가능

✅ **B.** 패스코드 설정된 기기에서만, 잠금 해제 시 접근

   **C.** 모든 기기에서 동기화

   **D.** 백업에 포함됨


**정답**: B


💡 **힌트**: 가장 높은 보안 수준으로, 패스코드가 설정되어 있고 잠금이 해제된 상태에서만 접근 가능합니다.


### 문제 2

Certificate Pinning에서 Public Key Pinning이 권장되는 이유는?


   **A.** 구현이 더 쉽다

✅ **B.** 인증서 갱신 시에도 공개키가 동일하면 동작한다

   **C.** 성능이 더 좋다

   **D.** 모든 도메인에 적용 가능하다


**정답**: B


💡 **힌트**: 인증서는 주기적으로 갱신되지만, 같은 키 쌍을 재사용하면 공개키는 변하지 않습니다.


