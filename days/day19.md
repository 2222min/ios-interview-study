# Day 19 — Design Patterns

**태그**: Observer · KVO · Combine · Builder · Strategy · Coordinator

---

## 📝 핵심 정리


### 1. Observer / KVO / Combine 비교

_아이콘: `blue`_


### 세 가지 관찰 패턴

iOS에서 "값이 변했을 때 알림을 받는" 방법은 크게 세 가지입니다. 각각의 특성과 적합한 상황이 다릅니다.

### 1. NotificationCenter (Observer 패턴)

```swift
// 발행
NotificationCenter.default.post(
    name: .userDidLogin,
    object: nil,
    userInfo: ["userId": "123"]
)

// 구독
let observer = NotificationCenter.default.addObserver(
    forName: .userDidLogin,
    object: nil,
    queue: .main
) { notification in
    let userId = notification.userInfo?["userId"] as? String
    print("로그인: \\(userId ?? "")")
}

// 해제 (iOS 9+ 에서는 자동이지만 명시적 해제 권장)
NotificationCenter.default.removeObserver(observer)
```

### 2. KVO (Key-Value Observing)

```swift
// NSObject 상속 + @objc dynamic 필요
class UserProfile: NSObject {
    @objc dynamic var name: String = ""
    @objc dynamic var score: Int = 0
}

// 관찰
let profile = UserProfile()
let observation = profile.observe(\\.score, options: [.new, .old]) { object, change in
    print("점수 변경: \\(change.oldValue ?? 0) → \\(change.newValue ?? 0)")
}

// observation이 해제되면 자동으로 관찰 중단
// 또는 observation.invalidate()
```

### 3. Combine (@Published)

```swift
class UserViewModel: ObservableObject {
    @Published var username: String = ""
    @Published var isValid: Bool = false
}

let vm = UserViewModel()
vm.$username
    .map { $0.count >= 3 }
    .assign(to: &vm.$isValid)

vm.$isValid
    .sink { print("유효성: \\($0)") }
    .store(in: &cancellables)
```

### 비교 표

| 항목 | NotificationCenter | KVO | Combine |
|---|---|---|---|
| 타입 안전 | ❌ (Any) | ⚠️ (KeyPath) | ✅ (Generic) |
| 1:N 관계 | ✅ 브로드캐스트 | ✅ 다수 관찰 | ✅ 다수 구독 |
| 변환/조합 | ❌ | ❌ | ✅ (map, filter 등) |
| NSObject 필요 | ❌ | ✅ | ❌ |
| 적합한 상황 | 시스템 이벤트, 느슨한 결합 | UIKit 프로퍼티 관찰 | 데이터 스트림, UI 바인딩 |

> 💡 **💡 면접 답변:** "NotificationCenter는 느슨한 결합이 필요한 시스템 이벤트에, KVO는 UIKit 프로퍼티(scrollView.contentOffset 등) 관찰에, Combine은 데이터 변환과 UI 바인딩에 적합합니다. 새 코드에서는 Combine을 우선 사용하고, 시스템 알림은 NotificationCenter를 유지합니다."


### 2. Builder & Strategy 패턴

_아이콘: `green`_


### Builder 패턴: 복잡한 객체 단계적 생성

```swift
// 네트워크 요청 빌더
class RequestBuilder {
    private var url: URL?
    private var method: HTTPMethod = .get
    private var headers: [String: String] = [:]
    private var body: Data?
    private var timeout: TimeInterval = 30
    
    @discardableResult
    func setURL(_ url: URL) -> Self {
        self.url = url
        return self
    }
    
    @discardableResult
    func setMethod(_ method: HTTPMethod) -> Self {
        self.method = method
        return self
    }
    
    @discardableResult
    func addHeader(key: String, value: String) -> Self {
        headers[key] = value
        return self
    }
    
    @discardableResult
    func setBody<T: Encodable>(_ body: T) -> Self {
        self.body = try? JSONEncoder().encode(body)
        return self
    }
    
    func build() throws -> URLRequest {
        guard let url = url else { throw BuilderError.missingURL }
        var request = URLRequest(url: url, timeoutInterval: timeout)
        request.httpMethod = method.rawValue
        request.allHTTPHeaderFields = headers
        request.httpBody = body
        return request
    }
}

// 사용
let request = try RequestBuilder()
    .setURL(URL(string: "https://api.example.com/users")!)
    .setMethod(.post)
    .addHeader(key: "Authorization", value: "Bearer \\(token)")
    .setBody(CreateUserDTO(name: "철수"))
    .build()
```

### Strategy 패턴: 알고리즘을 교체 가능하게

```swift
// 정렬 전략
protocol SortStrategy {
    func sort(_ items: [Item]) -> [Item]
}

class DateSortStrategy: SortStrategy {
    func sort(_ items: [Item]) -> [Item] {
        items.sorted { $0.date > $1.date }
    }
}

class PriceSortStrategy: SortStrategy {
    func sort(_ items: [Item]) -> [Item] {
        items.sorted { $0.price < $1.price }
    }
}

class PopularitySortStrategy: SortStrategy {
    func sort(_ items: [Item]) -> [Item] {
        items.sorted { $0.viewCount > $1.viewCount }
    }
}

// Context: 전략을 사용하는 클래스
class ProductListViewModel {
    private var sortStrategy: SortStrategy = DateSortStrategy()
    private var allItems: [Item] = []
    
    var displayItems: [Item] {
        sortStrategy.sort(allItems)
    }
    
    func changeSortOrder(_ strategy: SortStrategy) {
        self.sortStrategy = strategy
        // UI 업데이트
    }
}

// 사용
viewModel.changeSortOrder(PriceSortStrategy())
```

> 💡 **💡 면접 답변:** "Builder 패턴은 복잡한 객체를 단계적으로 구성할 때 사용합니다. @discardableResult와 Self 반환으로 메서드 체이닝을 구현합니다. Strategy 패턴은 동일한 인터페이스로 알고리즘을 교체할 때 사용합니다. 정렬, 유효성 검증, 가격 계산 등 런타임에 로직이 바뀌는 경우에 적합합니다."


### 3. Coordinator 패턴

_아이콘: `purple`_


### Coordinator란?

화면 전환(Navigation) 로직을 ViewController에서 분리하여 **별도 객체가 관리**하도록 하는 패턴입니다. ViewController는 "다음에 뭘 보여줄지" 모르고, Coordinator가 결정합니다.

### 기본 구조

```swift
protocol Coordinator: AnyObject {
    var childCoordinators: [Coordinator] { get set }
    var navigationController: UINavigationController { get set }
    func start()
}

// 앱 전체를 관리하는 메인 Coordinator
class AppCoordinator: Coordinator {
    var childCoordinators: [Coordinator] = []
    var navigationController: UINavigationController
    
    init(navigationController: UINavigationController) {
        self.navigationController = navigationController
    }
    
    func start() {
        if AuthManager.shared.isLoggedIn {
            showMainFlow()
        } else {
            showLoginFlow()
        }
    }
    
    private func showLoginFlow() {
        let loginCoordinator = LoginCoordinator(navigationController: navigationController)
        loginCoordinator.delegate = self
        childCoordinators.append(loginCoordinator)
        loginCoordinator.start()
    }
    
    private func showMainFlow() {
        let mainCoordinator = MainTabCoordinator(navigationController: navigationController)
        childCoordinators.append(mainCoordinator)
        mainCoordinator.start()
    }
}

// 로그인 플로우 Coordinator
class LoginCoordinator: Coordinator {
    var childCoordinators: [Coordinator] = []
    var navigationController: UINavigationController
    weak var delegate: LoginCoordinatorDelegate?
    
    init(navigationController: UINavigationController) {
        self.navigationController = navigationController
    }
    
    func start() {
        let loginVC = LoginViewController()
        loginVC.delegate = self
        navigationController.pushViewController(loginVC, animated: true)
    }
}

extension LoginCoordinator: LoginViewControllerDelegate {
    func didTapSignUp() {
        let signUpVC = SignUpViewController()
        signUpVC.delegate = self
        navigationController.pushViewController(signUpVC, animated: true)
    }
    
    func didLoginSuccessfully() {
        delegate?.loginDidComplete(self)
    }
}
```

### Coordinator의 장점

- **ViewController 경량화**: 화면 전환 코드 제거

- **재사용성**: 같은 VC를 다른 플로우에서 재사용 가능

- **테스트 용이**: Navigation 로직을 독립적으로 테스트

- **Deep Link 처리**: Coordinator가 직접 원하는 화면으로 이동

### Child Coordinator 해제

```swift
// 중요: child가 끝나면 반드시 배열에서 제거
extension AppCoordinator: LoginCoordinatorDelegate {
    func loginDidComplete(_ coordinator: LoginCoordinator) {
        childCoordinators.removeAll { $0 === coordinator }
        showMainFlow()
    }
}
```

> 💡 **💡 면접 답변:** "Coordinator 패턴은 화면 전환 로직을 ViewController에서 분리합니다. VC는 사용자 액션을 delegate로 전달하고, Coordinator가 다음 화면을 결정합니다. 이렇게 하면 VC 간 의존성이 사라져 재사용이 쉽고, Deep Link 처리도 Coordinator에서 일관되게 관리할 수 있습니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. Coordinator 패턴에서 메모리 관리 주의점은? `[기본 / 빈출]`

**childCoordinators 배열에서 완료된 Coordinator를 제거해야 합니다.**

Coordinator는 childCoordinators 배열로 자식을 strong 참조합니다. 자식 플로우가 끝났는데 배열에서 제거하지 않으면 메모리 누수가 발생합니다.

또한 delegate는 반드시 weak로 선언해야 합니다. parent ↔ child 간 순환 참조를 방지하기 위해서입니다.


### Q2. Strategy 패턴과 State 패턴의 차이는? `[심화]`

**의도가 다릅니다.**

• **Strategy**: 클라이언트가 명시적으로 알고리즘을 선택/교체. '어떻게 할 것인가'에 초점
• **State**: 객체의 내부 상태에 따라 행동이 자동으로 변경. '현재 상태가 무엇인가'에 초점

예시:
• Strategy: 사용자가 정렬 방식을 선택 (가격순, 날짜순)
• State: 주문 상태에 따라 가능한 액션이 변경 (대기→결제→배송→완료)


### Q3. Builder 패턴을 Swift에서 대체할 수 있는 방법은? `[심화 / 빈출]`

**Swift의 기본 파라미터와 구조체로 대체 가능한 경우가 많습니다.**

1. **기본 파라미터**: init(url:, method: .get, timeout: 30)
2. **구조체 + mutating**: 설정 구조체를 만들어 전달
3. **Result Builder**: SwiftUI의 @ViewBuilder처럼 DSL 구성

Builder가 여전히 유용한 경우:
• 생성 단계가 복잡하고 순서가 중요할 때
• 유효성 검증이 build() 시점에 필요할 때
• 같은 빌더로 다양한 변형을 만들 때


### Q4. NotificationCenter의 단점은? `[기본 / 빈출]`

**타입 안전성이 없고 추적이 어렵습니다.**

1. **타입 불안전**: userInfo가 [AnyHashable: Any]라서 런타임 캐스팅 필요
2. **추적 어려움**: 누가 post하고 누가 observe하는지 코드만 봐서는 파악 어려움
3. **순서 보장 없음**: 여러 observer의 실행 순서가 불확정
4. **해제 누락 위험**: removeObserver를 빠뜨리면 크래시 가능 (iOS 9 이전)

대안: Combine의 PassthroughSubject로 타입 안전한 이벤트 버스 구현


---


## ✏️ 퀴즈


### 문제 1

Coordinator 패턴에서 ViewController의 역할은?


   **A.** 다음 화면을 직접 push한다

✅ **B.** 사용자 액션을 delegate로 전달한다

   **C.** Navigation 스택을 관리한다

   **D.** 다른 VC를 직접 생성한다


**정답**: B


💡 **힌트**: VC는 '무엇이 일어났는지'만 알리고, '다음에 뭘 할지'는 Coordinator가 결정합니다.


### 문제 2

KVO가 Combine보다 적합한 경우는?


   **A.** 새로운 Swift 프로젝트

✅ **B.** UIScrollView의 contentOffset 관찰

   **C.** 데이터 변환이 필요할 때

   **D.** 여러 스트림을 조합할 때


**정답**: B


💡 **힌트**: UIKit의 기존 프로퍼티는 @objc dynamic으로 선언되어 있어 KVO로 직접 관찰 가능합니다.


