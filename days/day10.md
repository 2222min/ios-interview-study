# Day 10 — Dependency Injection과 모듈화

**태그**: DI · Constructor Injection · Tuist · Interface Module · Build Time

---

## 📝 핵심 정리


### 1. DI (Dependency Injection) 기초

_아이콘: `blue`_


### Dependency Injection이 뭔가요?

"객체가 필요한 의존성을 직접 만들지 않고, 외부에서 주입받는다"는 디자인 원칙입니다.

### 왜 필요한가요?

```swift
// ❌ 직접 의존: 테스트 불가
class UserViewModel {
    let networkService = NetworkService()  // 직접 인스턴스화
    
    func fetch() {
        networkService.request(...)
    }
}
// 문제:
// - 테스트할 때 가짜 NetworkService로 교체 불가
// - 다른 NetworkService 사용 불가 (캐싱, mocking)
// - UserViewModel이 NetworkService의 구체 구현에 강결합

// ✅ 의존성 주입: 테스트 가능, 유연
protocol NetworkServiceProtocol {
    func request(...) async throws -> Data
}

class UserViewModel {
    let networkService: NetworkServiceProtocol
    
    init(networkService: NetworkServiceProtocol) {
        self.networkService = networkService
    }
}

// 실제 사용
let vm = UserViewModel(networkService: NetworkService())

// 테스트
let mock = MockNetworkService()
let testVM = UserViewModel(networkService: mock)
```

### 3가지 주입 방식

### 1. Constructor Injection (가장 권장)

```swift
class FeedViewModel {
    private let repository: FeedRepositoryProtocol
    private let analytics: AnalyticsProtocol
    
    init(repository: FeedRepositoryProtocol, 
         analytics: AnalyticsProtocol) {
        self.repository = repository
        self.analytics = analytics
    }
}
// 장점: 의존성이 명확, 불변성 보장, 테스트 용이
// 단점: 의존성 많으면 init 파라미터 폭발
```

### 2. Property Injection

```swift
class FeedViewController: UIViewController {
    var viewModel: FeedViewModelProtocol!  // 외부에서 주입
}

// 사용
let vc = FeedViewController()
vc.viewModel = FeedViewModel(...)
// 장점: storyboard로 만든 ViewController에 적합 (init 못 건드림)
// 단점: nil 가능성, 주입 시점 불명확
```

### 3. Method Injection

```swift
class DataProcessor {
    func process(data: Data, using parser: ParserProtocol) -> Result {
        return parser.parse(data)
    }
}
// 장점: 호출마다 다른 의존성 사용 가능
// 단점: 매번 전달해야 함
```

### SOLID의 D: Dependency Inversion

"고수준 모듈은 저수준 모듈에 의존하면 안 되고, 둘 다 추상(인터페이스)에 의존해야 한다"는 원칙. DI가 이를 실현하는 메커니즘입니다.

> 💡 **💡 면접 포인트:** "DI는 단순히 'init 파라미터로 받는다'가 아니라, 결합도를 낮추고 테스트 가능성을 높이는 설계 철학입니다. Constructor Injection이 가장 안전하고 명확하지만, 의존성이 많아지면 Property Injection이나 DI Container를 고려할 수 있죠."


### 2. DI Container와 @propertyWrapper

_아이콘: `green`_


### DI Container가 뭔가요?

의존성을 한 곳에서 등록하고, 필요할 때 꺼내 쓰는 중앙 저장소입니다. Swinject 같은 라이브러리를 쓰거나 직접 구현할 수 있습니다.

### 간단한 DI Container 구현

```swift
final class DIContainer {
    static let shared = DIContainer()
    
    private var factories: [String: () -> Any] = [:]
    private var singletons: [String: Any] = [:]
    
    // 매번 새 인스턴스 (factory)
    func register<T>(_ type: T.Type, factory: @escaping () -> T) {
        let key = String(describing: type)
        factories[key] = factory
    }
    
    // 단일 인스턴스 공유 (singleton)
    func registerSingleton<T>(_ type: T.Type, factory: @escaping () -> T) {
        let key = String(describing: type)
        singletons[key] = factory()
    }
    
    func resolve<T>(_ type: T.Type) -> T {
        let key = String(describing: type)
        if let singleton = singletons[key] as? T {
            return singleton
        }
        guard let factory = factories[key],
              let instance = factory() as? T else {
            fatalError("No registration for \\(key)")
        }
        return instance
    }
}

// 등록 (앱 시작 시)
DIContainer.shared.registerSingleton(NetworkServiceProtocol.self) {
    NetworkService()
}
DIContainer.shared.register(FeedRepositoryProtocol.self) {
    FeedRepository(
        network: DIContainer.shared.resolve(NetworkServiceProtocol.self)
    )
}

// 사용
let repo = DIContainer.shared.resolve(FeedRepositoryProtocol.self)
```

### @propertyWrapper 기반 DI

```swift
@propertyWrapper
struct Injected<T> {
    private var value: T?
    
    init() {}
    
    var wrappedValue: T {
        mutating get {
            if let v = value { return v }
            let resolved = DIContainer.shared.resolve(T.self)
            value = resolved
            return resolved
        }
        set { value = newValue }
    }
}

// 사용 — 깔끔하다!
class FeedViewModel {
    @Injected var repository: FeedRepositoryProtocol
    @Injected var analytics: AnalyticsProtocol
}
```

### Service Locator 안티패턴 주의

DIContainer를 직접 호출하면 의존성이 숨겨집니다. 가능하면 Constructor Injection으로 명시적으로 받는 게 좋습니다.

```swift
// ❌ Service Locator (의존성이 숨겨짐)
class BadViewModel {
    func fetch() {
        let service = DIContainer.shared.resolve(NetworkServiceProtocol.self)
        // 이 클래스가 NetworkService에 의존하는지 외부에서 알기 어려움
    }
}

// ✅ Constructor Injection (의존성 명시적)
class GoodViewModel {
    let service: NetworkServiceProtocol
    init(service: NetworkServiceProtocol) {
        self.service = service
    }
}
```

> 💡 **💡 면접 포인트:** "DI Container는 편하지만 남용하면 Service Locator 안티패턴이 됩니다. Container는 앱 진입점(Composition Root)에서만 사용하고, 비즈니스 로직 안에서는 Constructor Injection으로 명시적으로 의존성을 받는 게 좋습니다."


### 3. Tuist 모듈화 전략

_아이콘: `purple`_


### 왜 모듈화가 필요한가요?

큰 앱(예: 100+ 화면)이 단일 타깃이면:

- 빌드 시간 매우 김 (작은 변경에도 전체 재컴파일)

- 여러 명이 같은 파일 수정 → 머지 충돌

- 의존 관계 파악 어려움 (모든 게 모든 걸 import 가능)

### 모듈 계층 구조

```swift
App
 ├─ Feature Modules (화면 단위)
 │   ├─ FeatureFeed
 │   ├─ FeatureProfile
 │   └─ FeatureSettings
 ├─ Domain Modules (비즈니스 로직)
 │   ├─ DomainFeed
 │   └─ DomainUser
 ├─ Core Modules (공통 유틸)
 │   ├─ CoreNetwork
 │   ├─ CoreUI
 │   └─ CoreStorage
 └─ Shared (확장, 상수)
```

### Tuist란?

Xcode 프로젝트 파일(`.xcodeproj`)을 코드(Swift)로 정의하고 자동 생성하는 도구입니다. 머지 충돌이 잦은 프로젝트 파일 문제를 해결합니다.

```swift
// Project.swift (Tuist manifest)
import ProjectDescription

let project = Project(
    name: "FeatureFeed",
    targets: [
        .target(
            name: "FeatureFeed",
            destinations: .iOS,
            product: .framework,
            bundleId: "com.app.featureFeed",
            sources: ["Sources/**"],
            dependencies: [
                .project(target: "DomainFeed", path: "../DomainFeed"),
                .project(target: "CoreUI", path: "../CoreUI")
            ]
        )
    ]
)
```

### Interface 모듈 패턴 (핵심!)

모듈 간 의존성을 최소화하기 위한 강력한 패턴입니다.

```swift
// ❌ 직접 의존: FeatureFeed → DomainUser
// FeatureFeed가 DomainUser의 모든 코드 변경에 영향받음

// ✅ Interface 분리:
//
// DomainUserInterface (Protocol만)
//   ↑
//   │ implements
//   │
// DomainUser (구현)
//
// FeatureFeed → DomainUserInterface (Protocol만 의존)

// DomainUserInterface 모듈 (가벼움)
public protocol UserServiceProtocol {
    func fetchUser(id: String) async throws -> UserEntity
}

public struct UserEntity {
    public let id: String
    public let name: String
}

// DomainUser 모듈 (실제 구현)
import DomainUserInterface

class UserService: UserServiceProtocol {  // internal 권장
    func fetchUser(id: String) async throws -> UserEntity { ... }
}
```

### Interface 분리의 효과

- **빌드 시간 단축**: FeatureFeed 빌드에 DomainUser 전체 빌드 불필요 (Interface만)

- **변경 영향 축소**: DomainUser 내부 변경 → FeatureFeed 재빌드 안 됨

- **Mock 생성 용이**: Interface만 있으면 됨

- **병렬 개발**: 팀 A가 Interface 정의, 팀 B는 구현, 팀 C는 사용 동시 진행

### Static vs Dynamic Framework

| 항목 | Static | Dynamic |
|---|---|---|
| 앱 시작 시간 | 빠름 (이미 링크됨) | 느림 (런타임 로딩) |
| 빌드 시간 | 느림 | 빠름 (분리됨) |
| 바이너리 크기 | 크게 됨 (중복 가능) | 작음 (공유) |

실무 가이드: 개발 빌드는 Dynamic (빠른 빌드), 배포 빌드는 Static (빠른 시작) — Tuist의 dev/release 분리 활용.

> 💡 **💡 면접 답변 예시:** "50개 이상의 모듈을 Tuist로 관리하며, Interface/Implementation 분리 패턴을 적용했습니다. 클린 빌드 12분 → 4분으로 단축했고, 증분 빌드는 30초 이내입니다. DI는 Swinject Assembly로 모듈별 의존성을 등록하고 앱 시작 시 조립하는 방식을 사용합니다. 핵심은 Interface 모듈이 매우 가볍게 유지되어야 빌드 캐싱 효과가 극대화된다는 점이죠."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. DI를 적용할 때 Constructor Injection을 권장하는 이유는? `[기본 / 빈출]`

네 가지 이유가 있습니다:

1. **의존성 명시**: init 파라미터로 모든 의존성이 드러남 → 외부에서 한눈에 파악
2. **불변성 보장**: `let`으로 선언 가능, 인스턴스 lifetime 동안 변경 안 됨
3. **테스트 용이**: Mock을 init에 전달만 하면 됨, 추가 설정 불필요
4. **nil 위험 없음**: Optional 없이 non-null 보장

단점은 의존성이 많을 때 init 파라미터가 길어지는 것. 이때는 Builder 패턴이나 DI Container를 고려할 수 있습니다.


### Q2. Service Locator 패턴이 안티패턴이라고 불리는 이유는? `[심화]`

**의존성이 숨겨지기 때문입니다.**

Service Locator를 사용하는 클래스는 init이나 메서드 시그니처에 의존성이 드러나지 않습니다. 코드 안에서 `Locator.resolve(...)`를 호출하므로 외부에서는 이 클래스가 무엇에 의존하는지 알기 어렵죠.

결과:
- 테스트 시 어떤 의존성을 mock해야 할지 불명확
- 의존성 분석 도구가 추적 못함
- 컴파일 타임에 누락 발견 못함

해결: DI Container는 Composition Root(앱 진입점)에서만 사용하고, 비즈니스 로직은 Constructor Injection으로 받기.


### Q3. Interface 모듈 분리의 핵심 효과는? `[심화 / 빈출]`

**빌드 캐싱 효과**입니다.

FeatureFeed가 DomainUser를 직접 의존하면, DomainUser의 어떤 작은 변경도 FeatureFeed의 재빌드를 유발합니다.

Interface 분리 후엔: FeatureFeed는 DomainUserInterface(Protocol만 있음)에만 의존. DomainUser의 구현 변경은 DomainUserInterface와 무관하므로 FeatureFeed 빌드 캐시 그대로 사용.

결과: 50개+ 모듈 환경에서 클린 빌드 12분 → 4분, 증분 빌드 30초 이내까지 단축 가능. 또한 Mock 생성도 Interface만 있으면 되어 테스트 용이성 증가.


### Q4. Static과 Dynamic Framework는 언제 어느 걸 쓰나요? `[심화]`

**일반적 가이드:**
- Feature 모듈 (자주 변경): Dynamic (빌드 캐시 효과)
- Core 모듈 (안정적, 광범위 사용): Static (앱 시작 빠름)

**제약:**
- iOS 앱은 Dynamic Framework 6개 이하 권장 (Apple)
- 그 이상이면 dyld 로딩 시간 영향 큼 → Static 전환

**실무 패턴:**
- 개발 빌드: 모두 Dynamic (빠른 빌드)
- 배포 빌드: Feature는 Dynamic, Core는 Static

Tuist에서는 `.framework(.static)`으로 명시 가능.


---


## ✏️ 퀴즈


### 문제 1

다음 중 가장 권장되는 DI 방식은?


   **A.** Service Locator (전역 컨테이너에서 직접 resolve)

   **B.** Property Injection

✅ **C.** Constructor Injection

   **D.** Singleton 사용


**정답**: C


💡 **힌트**: 의존성을 명시적으로 드러내면서 불변성을 보장하는 방식입니다.


### 문제 2

Interface 모듈 패턴의 가장 큰 장점은?


   **A.** 코드 양이 줄어든다

✅ **B.** 빌드 시간이 단축된다

   **C.** 런타임 성능이 향상된다

   **D.** 런타임 메모리가 줄어든다


**정답**: B


💡 **힌트**: 의존성 변경 시 영향 범위를 최소화하여 빌드 캐시 효과를 극대화합니다.


