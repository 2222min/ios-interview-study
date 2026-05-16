# Day 17 — App Launch Time 최적화

**태그**: dyld · pre-main · Static Framework · Dynamic Framework · lazy initialization

---

## 📝 핵심 정리


### 1. dyld 로딩과 pre-main 시간

_아이콘: `blue`_


### 앱 실행 과정 (pre-main)

사용자가 앱 아이콘을 탭한 순간부터 main() 함수가 호출되기까지의 시간입니다. Apple은 **400ms 이내**를 권장합니다.

```swift
// 앱 실행 단계
//
// ┌─────────────────────────────────────────────┐
// │ 1. Kernel: 프로세스 생성, ASLR 적용          │
// ├─────────────────────────────────────────────┤
// │ 2. dyld: Dynamic Linker                     │
// │    ├─ Load dylibs (동적 라이브러리 로드)      │
// │    ├─ Rebase (ASLR 오프셋 적용)             │
// │    ├─ Bind (외부 심볼 연결)                  │
// │    └─ ObjC Runtime (클래스 등록, 카테고리)    │
// ├─────────────────────────────────────────────┤
// │ 3. Static Initializers (+load, __attribute__)│
// ├─────────────────────────────────────────────┤
// │ 4. main() 호출                              │
// ├─────────────────────────────────────────────┤
// │ 5. UIApplicationMain                        │
// │    ├─ AppDelegate 초기화                     │
// │    ├─ didFinishLaunchingWithOptions          │
// │    └─ 첫 화면 렌더링                         │
// └─────────────────────────────────────────────┘
```

### pre-main 시간 측정

```swift
// Xcode에서 측정: Edit Scheme → Run → Arguments
// Environment Variables에 추가:
// DYLD_PRINT_STATISTICS = 1

// 출력 예시:
// Total pre-main time: 1.2 seconds (100.0%)
//          dylib loading time: 350ms (29.1%)
//         rebase/binding time:  80ms (6.6%)
//     ObjC setup time:         120ms (10.0%)
//          initializer time:   650ms (54.1%)
//          slowest intializers:
//            libSystem.B.dylib:   8ms
//            libMainThreadChecker: 42ms
//            MyApp:              580ms
```

### dyld 3 / dyld 4 개선사항

- **Launch Closure 캐싱**: 첫 실행 시 분석 결과를 캐싱하여 이후 실행 가속

- **Pre-warming**: iOS 15+에서 시스템이 앱을 미리 부분 실행

- **dyld shared cache**: 시스템 프레임워크를 미리 최적화하여 공유

> 💡 **💡 면접 포인트:** "pre-main 시간은 DYLD_PRINT_STATISTICS로 측정합니다. dylib 로딩, rebase/binding, ObjC 런타임 설정, static initializer 순서로 실행됩니다. Dynamic Framework 수를 줄이고, +load 메서드를 제거하며, 불필요한 ObjC 클래스를 정리하는 것이 핵심 최적화입니다."


### 2. Static vs Dynamic Framework

_아이콘: `green`_


### Static Framework

빌드 시 앱 바이너리에 **코드가 복사**됩니다. 실행 시 별도 로딩이 필요 없습니다.

### Dynamic Framework

별도 바이너리로 존재하며, **실행 시 dyld가 로드**합니다. 로딩 시간이 추가됩니다.

```swift
// 비교
// Static Framework:
// ┌──────────────────┐
// │   MyApp Binary   │
// │  ┌────────────┐  │
// │  │ FrameworkA │  │  ← 코드가 앱에 포함됨
// │  │ FrameworkB │  │
// │  └────────────┘  │
// └──────────────────┘
// 장점: 실행 시 로딩 없음, 앱 시작 빠름
// 단점: 앱 바이너리 크기 증가, 빌드 시간 증가

// Dynamic Framework:
// ┌──────────────────┐  ┌────────────┐
// │   MyApp Binary   │  │ FrameworkA │  ← 별도 파일
// │   (참조만 포함)   │  │ FrameworkB │
// └──────────────────┘  └────────────┘
// 장점: 코드 공유 가능, 빌드 캐시 효과
// 단점: dyld 로딩 시간 추가
```

### Apple 권장사항

```swift
// Dynamic Framework 개수 제한
// Apple WWDC 2016: "6개 이하 권장"
// 각 Dynamic Framework 로딩에 약 10~30ms 소요
// 20개면 200~600ms가 pre-main에 추가됨

// 실무 전략:
// 1. Feature 모듈: Static (앱 시작 영향 없음)
// 2. Core/공유 모듈: Static (광범위 사용)
// 3. 개발 빌드: Dynamic (빠른 증분 빌드)
// 4. 릴리즈 빌드: Static (빠른 앱 시작)
```

### Tuist/SPM에서 설정

```swift
// SPM: 기본 Static, Dynamic으로 변경 가능
let package = Package(
    products: [
        .library(name: "MyLib", type: .static, targets: ["MyLib"]),
        .library(name: "MyDynLib", type: .dynamic, targets: ["MyDynLib"])
    ]
)

// Tuist
let framework = Target(
    name: "FeatureHome",
    product: .staticFramework,  // 또는 .framework (dynamic)
    ...
)
```

> 💡 **💡 면접 답변:** "Static Framework는 앱 바이너리에 포함되어 실행 시 로딩이 없고, Dynamic Framework는 dyld가 런타임에 로드합니다. 릴리즈 빌드에서는 Static을 사용하여 앱 시작 시간을 최적화하고, 개발 빌드에서는 Dynamic으로 빌드 시간을 단축합니다. Apple은 Dynamic Framework를 6개 이하로 권장합니다."


### 3. Lazy Initialization 패턴

_아이콘: `orange`_


### 앱 시작 시 모든 것을 초기화하지 마세요

didFinishLaunchingWithOptions에서 모든 SDK와 서비스를 초기화하면 앱 시작이 느려집니다. **실제로 필요한 시점까지 초기화를 지연**하는 것이 핵심입니다.

### Lazy 초기화 전략

```swift
// ❌ 모든 것을 앱 시작 시 초기화
func application(_ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    
    FirebaseApp.configure()          // 200ms
    Crashlytics.configure()          // 50ms
    AnalyticsSDK.initialize()        // 100ms
    PushNotification.register()      // 30ms
    DeepLinkManager.setup()          // 20ms
    ABTestingSDK.initialize()        // 80ms
    // 총 480ms 추가!
    return true
}

// ✅ 우선순위별 분리
func application(_ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    
    // Phase 1: 필수 (첫 화면 표시에 필요)
    CoreDataStack.shared.setup()
    AuthManager.shared.restoreSession()
    
    return true
}

// Phase 2: 첫 화면 표시 후
func applicationDidBecomeActive(_ application: UIApplication) {
    DispatchQueue.main.async {
        FirebaseApp.configure()
        Crashlytics.configure()
    }
}

// Phase 3: 실제 사용 시점 (Lazy)
class AnalyticsManager {
    static let shared: AnalyticsManager = {
        let manager = AnalyticsManager()
        manager.initialize()  // 첫 접근 시에만 초기화
        return manager
    }()
}
```

### Swift의 lazy 키워드 활용

```swift
class ViewController: UIViewController {
    // 화면에 표시될 때만 생성
    lazy var heavyView: ComplexChartView = {
        let view = ComplexChartView()
        view.configure(with: chartData)
        return view
    }()
    
    // 필요할 때만 생성되는 포맷터
    lazy var dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "ko_KR")
        return formatter
    }()
}

// 주의: lazy는 thread-safe하지 않음!
// 여러 스레드에서 동시 접근 시 두 번 초기화될 수 있음
// 해결: static let (dispatch_once 보장)
class Singleton {
    static let shared = Singleton()  // thread-safe
    private init() { }
}
```

### Launch Time 측정 도구

- **DYLD_PRINT_STATISTICS**: pre-main 시간 분석

- **Instruments → App Launch**: 전체 실행 과정 프로파일링

- **MetricKit**: 실제 사용자 기기에서의 실행 시간 수집

- **os_signpost**: 커스텀 구간 측정

> 💡 **💡 면접 답변:** "앱 시작 최적화는 세 단계로 접근합니다. 첫째, pre-main 최적화(Dynamic Framework 줄이기, +load 제거). 둘째, didFinishLaunching 최소화(필수 초기화만). 셋째, lazy initialization으로 나머지를 지연. 저는 이 전략으로 앱 시작 시간을 2.1초에서 0.8초로 단축한 경험이 있습니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. 앱 시작 시간 최적화에서 가장 효과적인 방법은? `[기본 / 빈출]`

**Dynamic Framework 수를 줄이는 것이 가장 효과적입니다.**

각 Dynamic Framework는 10~30ms의 로딩 시간을 추가합니다. 20개를 Static으로 전환하면 200~600ms를 절약할 수 있습니다.

그 다음으로:
1. didFinishLaunching에서 불필요한 초기화 제거/지연
2. +load 메서드를 +initialize로 교체
3. 사용하지 않는 ObjC 클래스 제거
4. Asset Catalog 최적화


### Q2. iOS 15의 pre-warming은 무엇인가요? `[심화 / 빈출]`

**시스템이 앱을 미리 부분적으로 실행하는 기능입니다.**

사용자가 앱을 탭하기 전에 시스템이 예측하여 dyld 로딩과 일부 초기화를 미리 수행합니다. 사용자가 실제로 앱을 열면 이미 완료된 단계를 건너뛰어 체감 시작 시간이 빨라집니다.

주의점:
• didFinishLaunching이 pre-warming 시점에 호출될 수 있음
• 이때 UI 작업을 하면 안 됨
• `ProcessInfo.processInfo.environment[\"ActivePrewarm\"]`로 감지 가능


### Q3. static let이 thread-safe한 이유는? `[심화]`

**Swift의 static let은 내부적으로 dispatch_once와 동일한 메커니즘을 사용합니다.**

컴파일러가 자동으로 동기화 코드를 삽입하여, 여러 스레드가 동시에 접근해도 초기화가 정확히 한 번만 실행됩니다.

반면 lazy var는 이런 보장이 없어서 여러 스레드에서 동시 접근하면 두 번 초기화될 수 있습니다. 싱글톤은 반드시 static let으로 구현해야 합니다.


---


## ✏️ 퀴즈


### 문제 1

Apple이 권장하는 Dynamic Framework 최대 개수는?


   **A.** 3개

✅ **B.** 6개

   **C.** 10개

   **D.** 제한 없음


**정답**: B


💡 **힌트**: WWDC 2016에서 Apple은 앱 시작 시간을 위해 이 수를 권장했습니다.


### 문제 2

DYLD_PRINT_STATISTICS로 측정할 수 있는 것은?


   **A.** 네트워크 응답 시간

✅ **B.** pre-main 시간 (dylib 로딩, rebase/binding 등)

   **C.** UI 렌더링 시간

   **D.** 메모리 사용량


**정답**: B


💡 **힌트**: main() 함수 호출 전까지의 시간을 단계별로 분석합니다.


