# Day 8 — 네트워킹: URLSession과 보안

**태그**: URLSession · HTTP/2 · Certificate Pinning · Cache · Background Session

---

## 📝 핵심 정리


### 1. URLSession 아키텍처

_아이콘: `blue`_


### URLSession의 계층 구조

```swift
URLSession (네트워크 작업의 진입점)
  └─ URLSessionConfiguration (설정: 타임아웃, 캐시 등)
      └─ URLSessionTask (실제 작업 단위)
          ├─ URLSessionDataTask (일반 데이터)
          ├─ URLSessionUploadTask (업로드)
          ├─ URLSessionDownloadTask (큰 파일 다운)
          └─ URLSessionWebSocketTask (WebSocket)
              └─ URLProtocol (실제 네트워크 처리)
                  └─ HTTP/2 Connection Pool
                      └─ TLS/TCP Socket
```

### 3가지 주요 Configuration

```swift
// .default - 일반 사용 (디스크 캐시, 쿠키 저장)
let config = URLSessionConfiguration.default

// .ephemeral - 메모리만 사용 (프라이빗 브라우징)
// 디스크에 아무것도 저장 안 됨
let private = URLSessionConfiguration.ephemeral

// .background - 앱 종료 후에도 전송 계속
// 시스템 데몬이 다운로드/업로드 처리
let bg = URLSessionConfiguration.background(
    withIdentifier: "com.app.upload"
)
```

### 주요 설정 옵션

```swift
let config = URLSessionConfiguration.default

// 타임아웃
config.timeoutIntervalForRequest = 30   // 응답 대기 시간
config.timeoutIntervalForResource = 300 // 전체 전송 완료 시간

// 동시 연결 제한
config.httpMaximumConnectionsPerHost = 4

// 캐시 정책
config.requestCachePolicy = .returnCacheDataElseLoad
config.urlCache = URLCache(
    memoryCapacity: 50 * 1024 * 1024,  // 50MB
    diskCapacity: 200 * 1024 * 1024     // 200MB
)

// 네트워크 대기 (iOS 11+)
config.waitsForConnectivity = true
// 네트워크 없으면 즉시 실패 대신 대기
// → urlSession(_:taskIsWaitingForConnectivity:) delegate 호출

// HTTP 헤더
config.httpAdditionalHeaders = [
    "Authorization": "Bearer \\(token)",
    "User-Agent": "MyApp/1.0"
]
```

### HTTP/2 멀티플렉싱

같은 호스트에 대한 여러 요청이 하나의 TCP 연결을 공유합니다.

| 버전 | 동작 |
|---|---|
| HTTP/1.1 | 호스트당 최대 6개 TCP 연결, 각각 핸드셰이크 비용 |
| HTTP/2 | 호스트당 1개 TCP, 여러 stream 멀티플렉싱 |
| HTTP/3 (QUIC) | UDP 기반, head-of-line blocking 해결 |

URLSession은 서버가 지원하면 자동으로 HTTP/2를 사용합니다.

> 💡 **💡 면접 포인트:** "URLSession은 단순 HTTP 클라이언트가 아니라 connection pool, 캐시, 인증, 백그라운드 전송까지 포함한 통합 시스템입니다. background configuration의 흥미로운 점은 앱이 죽어도 시스템 데몬이 전송을 마치고 완료 시 앱을 깨워준다는 거예요. 큰 업로드/다운로드에 필수입니다."


### 2. Certificate Pinning (인증서 피닝)

_아이콘: `green`_


### 왜 필요한가요?

일반 HTTPS는 시스템이 신뢰하는 모든 CA가 발급한 인증서를 받아들입니다. 하지만:

- 회사 프록시(charles, mitmproxy)가 자체 CA를 설치하면 → MITM 공격 가능

- 악성 CA가 발급한 인증서로 가짜 서버 가능

인증서 피닝은 "내가 미리 알고 있는 특정 인증서/키만 받아들인다"고 명시하는 추가 보안 계층입니다.

### 피닝의 두 가지 방식

| 방식 | 장점 | 단점 |
|---|---|---|
| Certificate Pinning | 구현 간단 | 인증서 갱신 시 앱 업데이트 |
| Public Key Pinning | 키 유지 시 인증서 갱신 OK | 구현 약간 복잡 |

### Public Key Pinning 구현

```swift
class NetworkDelegate: NSObject, URLSessionDelegate {
    
    // 서버 공개키의 SHA-256 해시 (현재 + 백업)
    let pinnedHashes: Set<String> = [
        "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",  // 현재
        "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC="   // 백업 (롤오버 대비)
    ]
    
    func urlSession(_ session: URLSession,
                    didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        
        // 서버 인증서 검증 단계
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // 서버 인증서에서 공개키 추출
        guard let serverCert = SecTrustGetCertificateAtIndex(serverTrust, 0),
              let publicKey = SecCertificateCopyKey(serverCert),
              let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, nil) as Data? else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }
        
        // SHA-256 해시 계산
        let hash = SHA256.hash(data: publicKeyData)
        let hashString = Data(hash).base64EncodedString()
        
        if pinnedHashes.contains(hashString) {
            // 매치! 정상 진행
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            // 매치 안 됨 → 연결 거부
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }
}

let session = URLSession(
    configuration: .default,
    delegate: NetworkDelegate(),
    delegateQueue: nil
)
```

### 중요: 백업 핀 필수

인증서/키는 보안 사고 시나 정기적으로 교체해야 합니다. 핀이 하나뿐이면 교체 시점에 앱이 모두 동작을 멈춥니다. 항상 2개 이상의 핀(현재 + 다음 갱신용)을 유지해야 합니다.

### Trade-off

- ✅ MITM 공격 차단

- ✅ 회사 프록시 우회 차단

- ❌ 인증서 갱신 시 앱 업데이트 필요

- ❌ Charles/Proxyman 디버깅 불가 (개발 빌드는 비활성화)

- ❌ 잘못 구현하면 모든 사용자가 앱 사용 불가

> 💡 **💡 면접 포인트:** "인증서 피닝은 강력한 추가 보안 계층이지만 양날의 검입니다. 핀이 잘못되거나 인증서 교체 누락 시 모든 사용자가 차단됩니다. 그래서 항상 2개 이상의 백업 핀을 두고, 서버에서 강제 업데이트 메커니즘을 별도로 마련합니다. 금융앱이나 의료앱 같은 고보안 도메인에선 거의 필수입니다."


### 3. HTTP 캐시와 효율적 네트워킹

_아이콘: `purple`_


### HTTP 캐시 정책

| 정책 | 동작 |
|---|---|
| `.useProtocolCachePolicy` | 기본값. 서버 Cache-Control 헤더 따름 |
| `.reloadIgnoringLocalCacheData` | 항상 서버 요청 |
| `.returnCacheDataElseLoad` | 캐시 우선, 없으면 네트워크 |
| `.returnCacheDataDontLoad` | 캐시만, 없으면 실패 (오프라인 모드) |

### 조건부 요청 (Conditional Request)

URLSession은 자동으로 ETag/Last-Modified를 처리합니다. 서버가 변경 없으면 304 Not Modified 응답 → 캐시 사용.

```swift
// 첫 요청
GET /api/data
Response 200 OK
ETag: "abc123"
[데이터]

// 두 번째 요청 (URLSession이 자동 처리)
GET /api/data
If-None-Match: "abc123"
Response 304 Not Modified  ← 본문 없음, 캐시 사용
```

### Reachability와 waitsForConnectivity

```swift
// 옛날 방식: Reachability
// 매번 네트워크 상태 체크 → 안 되면 에러

// 현재: NWPathMonitor (Network framework)
import Network
let monitor = NWPathMonitor()
monitor.pathUpdateHandler = { path in
    if path.status == .satisfied {
        print("네트워크 연결됨")
        if path.usesInterfaceType(.cellular) {
            print("셀룰러 연결")
        }
    } else {
        print("네트워크 끊김")
    }
}
monitor.start(queue: DispatchQueue.global())

// URLSession: waitsForConnectivity로 자동 대기
let config = URLSessionConfiguration.default
config.waitsForConnectivity = true
// 네트워크 없으면 즉시 실패 안 하고 대기 → 연결되면 자동 진행
```

### 실무 네트워크 레이어 구조

```swift
// 1. Endpoint enum
enum Endpoint {
    case getUser(id: String)
    case updateProfile(data: ProfileData)
    
    var path: String { ... }
    var method: HTTPMethod { ... }
    var body: Data? { ... }
}

// 2. NetworkService protocol (테스트 용이)
protocol NetworkServiceProtocol {
    func request<T: Decodable>(_ endpoint: Endpoint) async throws -> T
}

// 3. 구현
class NetworkService: NetworkServiceProtocol {
    private let session: URLSession
    
    func request<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        let request = endpoint.urlRequest
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              200..<300 ~= httpResponse.statusCode else {
            throw NetworkError.serverError
        }
        
        return try JSONDecoder().decode(T.self, from: data)
    }
}
```

> 💡 **💡 면접 포인트:** "네트워크 레이어는 Endpoint enum + Protocol 추상화로 만들면 테스트와 변경에 유연합니다. URLSession의 캐시 정책을 적절히 활용하면 서버 부하와 사용자 대기 시간을 줄일 수 있고, waitsForConnectivity는 네트워크가 끊겼다가 다시 연결될 때 자동 재시도해줘서 UX 향상에 유용합니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. URLSession의 delegate queue가 nil이면 어떻게 되나요? `[심화]`

시스템이 serial OperationQueue를 자동으로 생성하여 delegate 콜백을 전달합니다. **이 큐는 메인 스레드가 아닙니다.**

그래서 delegate 콜백에서 UI 업데이트를 하려면 `DispatchQueue.main.async`로 디스패치해야 합니다.

완전히 메인 스레드에서 받고 싶다면 `OperationQueue.main`을 명시적으로 전달하세요. 단, completion handler 기반 API(data(for:))는 await 후 호출자의 actor에서 재개되므로 별개 동작합니다.


### Q2. Background URLSession의 동작 원리는? `[심화 / 빈출]`

Background Configuration으로 만든 URLSession은 `nsurlsessiond`라는 시스템 데몬이 실제 네트워크 작업을 처리합니다.

특징:
- 앱이 백그라운드/종료되어도 전송 계속됨
- 시스템이 네트워크/배터리 상태에 따라 최적 시점 선택
- 완료/실패 시 `application(_:handleEventsForBackgroundURLSession:)`로 앱을 깨움
- 같은 identifier로 다시 만들면 진행 중인 작업과 연결됨

주의: completion handler 기반은 사용 불가, delegate 패턴만 가능. `isDiscretionary = true`로 설정하면 시스템이 더 적극적으로 최적화.


### Q3. 인증서 피닝은 왜 백업 핀이 필요한가요? `[심화 / 빈출]`

인증서/공개키는 다음 이유로 교체될 수 있습니다:
- 정기 갱신 (보통 1~2년 주기)
- 보안 사고로 인한 긴급 교체
- 서버 마이그레이션

핀이 하나뿐이면 교체 순간 모든 클라이언트가 연결 실패합니다.

해결: 항상 \"현재 핀\"과 \"다음 갱신용 핀\" 2개 이상을 앱에 포함. 서버 측 강제 업데이트 메커니즘도 별도로 마련해 비상 대응 가능하게 합니다.


### Q4. HTTP/2의 멀티플렉싱이란? `[기본]`

하나의 TCP 연결 위에 여러 개의 독립적인 stream을 동시에 흐르게 하는 기술입니다.

HTTP/1.1: 한 요청 끝나야 다음 요청 시작 (또는 호스트당 최대 6 연결로 회피)
HTTP/2: 한 연결로 여러 요청을 동시에 (응답 순서 무관)

장점:
- TCP 핸드셰이크 비용 절감
- TLS 핸드셰이크 한 번만
- Head-of-line blocking 부분 해결

여전히 TCP 레벨에서 패킷 손실 시 모든 stream이 영향. 이걸 완전히 해결한 게 HTTP/3 (QUIC, UDP 기반).


---


## ✏️ 퀴즈


### 문제 1

URLSession의 background configuration이 가장 적합한 용도는?


   **A.** 빠른 API 호출

✅ **B.** 대용량 파일 다운로드/업로드

   **C.** WebSocket 연결

   **D.** localhost 통신


**정답**: B


💡 **힌트**: 앱이 종료되어도 시스템이 전송을 마치게 해야 하는 경우입니다.


### 문제 2

Public Key Pinning을 구현할 때 가장 중요한 것은?


   **A.** 가능한 많은 핀을 등록한다

✅ **B.** 최소 2개 이상의 백업 핀을 유지한다

   **C.** 인증서 자체의 해시를 사용한다

   **D.** Charles 같은 디버깅 도구가 항상 동작하도록 한다


**정답**: B


💡 **힌트**: 인증서 갱신 시 앱이 동작하지 않게 되는 사고를 방지하려면?


