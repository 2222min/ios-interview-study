# Day 9 — 아키텍처 패턴: MVC, MVVM, Clean Architecture

**태그**: MVC · MVVM · Clean Architecture · Coordinator · TCA

---

## 📝 핵심 정리


### 1. MVC와 그 한계 (Massive View Controller)

_아이콘: `blue`_


### 전통적인 MVC

```swift
// 이론적 MVC:
//
// Model ←──→ Controller ←──→ View
//
// Model: 비즈니스 데이터
// View: 화면 표시
// Controller: 둘 사이 중재
```

### Apple의 MVC = Massive View Controller

iOS에서는 ViewController가 거의 모든 일을 떠안게 됩니다. 결과는 1000줄+의 거대한 파일.

```swift
// 흔한 ViewController의 책임 (모두 한 클래스에...):
class FeedViewController: UIViewController {
    // 1. View lifecycle
    override func viewDidLoad() { ... }
    
    // 2. UI 구성
    private let tableView = UITableView()
    private func setupUI() { ... }
    
    // 3. 데이터 모델
    private var items: [FeedItem] = []
    
    // 4. 네트워크 요청
    func fetchData() {
        URLSession.shared.dataTask(with: url) { ... }
    }
    
    // 5. 데이터 변환 (DTO → 표시 모델)
    func transform(_ dto: FeedDTO) -> FeedItem { ... }
    
    // 6. 비즈니스 로직
    func validateAndSave(_ item: FeedItem) { ... }
    
    // 7. UITableViewDataSource
    func numberOfSections... { ... }
    
    // 8. UITableViewDelegate
    func tableView(_:didSelectRowAt:) { ... }
    
    // 9. 네비게이션
    func showDetail(_ item: FeedItem) {
        navigationController?.pushViewController(...)
    }
    
    // ... 1500줄짜리 파일 완성
}
```

### 왜 문제인가요?

- 테스트 불가능 (UIKit 의존, 모든 게 하나에 묶임)

- 재사용 불가

- 여러 명이 같은 파일 수정 → 머지 충돌

- 변경 영향 범위 파악 어려움

### MVC가 적합한 경우

- 단순한 화면 (설정, 정적 목록)

- 프로토타이핑

- 1~2명 작은 팀, 단기 프로젝트

> 💡 **💡 면접 포인트:** "Apple의 MVC가 나쁜 건 아닙니다. 단지 iOS의 UIViewController가 View와 Controller의 역할을 동시에 가지면서 책임이 너무 많아진 것뿐이죠. 이를 분리하기 위해 MVVM, VIPER, Clean Architecture 같은 패턴이 등장했습니다."


### 2. MVVM + Coordinator

_아이콘: `green`_


### MVVM 구조

```swift
// View (ViewController) ←─바인딩─→ ViewModel ←─→ Model/Repository
//
// View: UI 렌더링, 사용자 입력 ViewModel에 전달
// ViewModel: 비즈니스 로직, 상태 관리. UIKit import 금지!
// Model: 데이터, 도메인 객체
```

### ViewModel 핵심 규칙

- **UIKit/SwiftUI import 금지**: 테스트 가능성 보장

- **View와 단방향 통신**: ViewModel → View는 binding, View → ViewModel은 메서드 호출

- **Input/Output 명확화**: 인터페이스를 protocol로 정의

### Input/Output 패턴 (RxSwift/Combine)

```swift
protocol ViewModelType {
    associatedtype Input
    associatedtype Output
    func transform(input: Input) -> Output
}

class FeedViewModel: ViewModelType {
    // 사용자 액션 (View → ViewModel)
    struct Input {
        let viewDidLoad: AnyPublisher<Void, Never>
        let pullToRefresh: AnyPublisher<Void, Never>
        let itemSelected: AnyPublisher<IndexPath, Never>
    }
    
    // ViewModel 출력 (ViewModel → View)
    struct Output {
        let items: AnyPublisher<[FeedItem], Never>
        let isLoading: AnyPublisher<Bool, Never>
        let error: AnyPublisher<String, Never>
    }
    
    private let repository: FeedRepositoryProtocol
    
    init(repository: FeedRepositoryProtocol) {
        self.repository = repository
    }
    
    func transform(input: Input) -> Output {
        // Input → Output 변환 로직
        let isLoading = CurrentValueSubject<Bool, Never>(false)
        
        let items = Publishers.Merge(input.viewDidLoad, input.pullToRefresh)
            .handleEvents(receiveOutput: { _ in isLoading.send(true) })
            .flatMap { [weak self] _ -> AnyPublisher<[FeedItem], Never> in
                self?.repository.fetchFeed() ?? Empty().eraseToAnyPublisher()
            }
            .handleEvents(receiveOutput: { _ in isLoading.send(false) })
            .eraseToAnyPublisher()
        
        return Output(
            items: items,
            isLoading: isLoading.eraseToAnyPublisher(),
            error: Empty().eraseToAnyPublisher()
        )
    }
}
```

### Coordinator 패턴 (네비게이션 분리)

ViewController가 다른 ViewController를 push/present하면 결합도가 높아집니다. Coordinator가 네비게이션을 전담합니다.

```swift
protocol Coordinator: AnyObject {
    var childCoordinators: [Coordinator] { get set }
    var navigationController: UINavigationController { get }
    func start()
}

class FeedCoordinator: Coordinator {
    var childCoordinators: [Coordinator] = []
    let navigationController: UINavigationController
    
    init(navigationController: UINavigationController) {
        self.navigationController = navigationController
    }
    
    func start() {
        let vm = FeedViewModel(repository: FeedRepository())
        let vc = FeedViewController(viewModel: vm)
        vc.delegate = self  // 화면 전환 요청 받기
        navigationController.pushViewController(vc, animated: true)
    }
}

extension FeedCoordinator: FeedViewControllerDelegate {
    func didSelectItem(_ item: FeedItem) {
        // 자식 Coordinator 만들어 위임
        let detail = DetailCoordinator(
            navigationController: navigationController,
            item: item
        )
        childCoordinators.append(detail)
        detail.start()
    }
}
```

### 장점

- ViewController가 화면 전환을 모름 → 재사용 가능

- 화면 흐름 변경이 Coordinator에서만 일어남

- Deep link 처리 용이

> 💡 **💡 면접 포인트:** "MVVM은 View의 책임을 분리하지만 화면 전환 로직은 여전히 애매합니다. Coordinator로 네비게이션을 추출하면 ViewController가 정말 화면 표시만 담당하게 되어 재사용성이 크게 올라갑니다. 단, 작은 앱에선 Coordinator가 오버엔지니어링일 수 있어요."


### 3. Clean Architecture

_아이콘: `purple`_


### Clean Architecture 원칙

Robert C. Martin(Uncle Bob)이 제안한 아키텍처. **핵심: 의존성은 항상 바깥에서 안쪽으로만 향한다.**

```swift
// 레이어 구조 (안쪽 → 바깥쪽):
//
// ┌─────────────────────────────────────────┐
// │  Frameworks (UIKit, URLSession...)       │  ← 가장 바깥
// │  ┌───────────────────────────────────┐   │
// │  │  Interface Adapters               │   │
// │  │  (Presenter, Gateway, Controller) │   │
// │  │  ┌─────────────────────────────┐  │   │
// │  │  │  Application Business Rules  │  │   │
// │  │  │  (Use Cases)                 │  │   │
// │  │  │  ┌──────────────────────┐    │  │   │
// │  │  │  │  Enterprise Rules    │    │  │   │
// │  │  │  │  (Entities)          │    │  │   │
// │  │  │  └──────────────────────┘    │  │   │
// │  │  └─────────────────────────────┘  │   │
// │  └───────────────────────────────────┘   │
// └─────────────────────────────────────────┘
//
// Entity는 누구도 의존 안 함 (가장 안쪽)
// Use Case는 Entity만 의존
// Adapter는 Use Case와 Entity 의존
// Framework는 모두 의존 (UI 같은 디테일)
```

### iOS 적용 예시

```swift
// Domain Layer (가장 안쪽, 프레임워크 의존성 없음)
struct User {  // Entity (순수 비즈니스 모델)
    let id: String
    let name: String
    let email: String
}

protocol UserRepository {  // Repository Protocol (인터페이스)
    func fetchUser(id: String) async throws -> User
    func saveUser(_ user: User) async throws
}

class FetchUserUseCase {  // Use Case (비즈니스 로직)
    private let repository: UserRepository
    
    init(repository: UserRepository) {
        self.repository = repository
    }
    
    func execute(id: String) async throws -> User {
        let user = try await repository.fetchUser(id: id)
        // 비즈니스 규칙 적용
        guard !user.name.isEmpty else { throw DomainError.invalidUser }
        return user
    }
}

// Data Layer (Repository 구현)
struct UserDTO: Decodable {  // 네트워크 응답 모델
    let id: String
    let full_name: String
    let email_address: String
    
    func toDomain() -> User {  // DTO → Entity 변환
        User(id: id, name: full_name, email: email_address)
    }
}

class UserRepositoryImpl: UserRepository {
    private let networkService: NetworkServiceProtocol
    private let cacheService: CacheServiceProtocol
    
    init(networkService: NetworkServiceProtocol,
         cacheService: CacheServiceProtocol) {
        self.networkService = networkService
        self.cacheService = cacheService
    }
    
    func fetchUser(id: String) async throws -> User {
        // 1. 캐시 확인
        if let cached: User = cacheService.get(key: "user_\\(id)") {
            return cached
        }
        // 2. 네트워크 요청
        let dto: UserDTO = try await networkService.request(.getUser(id: id))
        // 3. DTO → Entity 변환
        let user = dto.toDomain()
        // 4. 캐싱
        cacheService.set(key: "user_\\(id)", value: user)
        return user
    }
}

// Presentation Layer
class UserDetailViewModel {
    private let fetchUserUseCase: FetchUserUseCase
    
    @Published var user: User?
    
    init(fetchUserUseCase: FetchUserUseCase) {
        self.fetchUserUseCase = fetchUserUseCase
    }
    
    func load(userId: String) async {
        do {
            user = try await fetchUserUseCase.execute(id: userId)
        } catch {
            // 에러 처리
        }
    }
}
```

### 장점

- UI 변경 → Domain 영향 없음

- 네트워크 라이브러리 교체 (URLSession → Alamofire) → Domain 영향 없음

- Domain 로직 100% 유닛 테스트 가능

- 대규모 팀에서 책임 분리 명확

### 단점

- 코드 양 증가 (DTO ↔ Entity 변환 등 보일러플레이트)

- 작은 앱에서는 오버엔지니어링

- 학습 곡선

> 💡 **💡 면접 답변 예시:** "저는 MVVM + Coordinator + Clean Architecture를 조합합니다. Domain 레이어는 순수 Swift로 유지해 테스트 커버리지 90% 이상 달성했고, Repository를 Protocol로 추상화하여 Mock 주입이 용이합니다. 모듈화는 Tuist로 관리하며, Feature 모듈 간 의존성은 Interface 모듈을 통해 간접 참조해서 빌드 시간을 12분에서 4분으로 단축했습니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. 왜 ViewModel에서 UIKit을 import하면 안 되나요? `[기본 / 빈출]`

세 가지 이유가 있습니다:

1. **테스트 가능성**: UIKit은 main thread, view hierarchy 등 환경에 의존. 유닛 테스트 환경에서 실행 어려움.
2. **플랫폼 독립성**: 같은 ViewModel을 macOS, watchOS, SwiftUI에서 재사용 가능.
3. **책임 분리**: ViewModel은 비즈니스 로직, View는 UI. 섞이면 MVC와 다를 바 없음.

대신 `UIImage`가 필요하면 `Data`나 URL로 추상화하고, 색상은 hex string이나 enum으로 표현합니다.


### Q2. Coordinator 패턴의 장단점은? `[기본]`

**장점:**
1. ViewController가 화면 전환을 모름 → 재사용 가능
2. 화면 흐름이 Coordinator에 집중 → 변경 용이
3. Deep link 처리 깔끔
4. ViewController 간 데이터 전달 명확

**단점:**
1. 코드 양 증가 (작은 앱엔 오버엔지니어링)
2. 학습 곡선
3. childCoordinators 메모리 관리 주의 (해제 누락 시 누수)
4. SwiftUI에선 NavigationStack/Path가 비슷한 역할 → 패턴 적용 방식 다름


### Q3. Clean Architecture의 의존성 규칙은? `[심화 / 빈출]`

**의존성은 항상 바깥에서 안쪽으로만 향한다.**

안쪽(Domain)은 바깥쪽(UI, 네트워크)을 모르고, 바깥쪽이 안쪽의 인터페이스(Protocol)를 구현합니다.

예: `UserRepository` protocol은 Domain 레이어, `UserRepositoryImpl`은 Data 레이어. ViewModel은 protocol에만 의존하고 구현은 DI로 주입받음.

이 규칙 덕분에 UI 라이브러리, 네트워크 라이브러리, DB를 교체해도 Domain 로직은 그대로 유지됩니다.


### Q4. TCA(The Composable Architecture)는 뭔가요? `[심화]`

PointFree에서 만든 SwiftUI 친화적 단방향 데이터 흐름 아키텍처입니다.

핵심 컨셉:
- **State**: 화면의 모든 상태
- **Action**: 발생할 수 있는 모든 이벤트
- **Reducer**: State + Action → 새 State (순수 함수)
- **Effect**: 부수 효과 (네트워크 등)
- **Store**: 위 요소들을 묶어 관리

장점: 강력한 테스트 가능성, Store 합성으로 큰 앱 구성 가능, 시간 여행 디버깅.
단점: 학습 곡선 가파름, 보일러플레이트, 작은 앱엔 오버엔지니어링.


---


## ✏️ 퀴즈


### 문제 1

MVVM에서 ViewModel이 절대 import하면 안 되는 것은?


   **A.** Foundation

   **B.** Combine

✅ **C.** UIKit

   **D.** Swift Standard Library


**정답**: C


💡 **힌트**: 테스트 가능성과 플랫폼 독립성을 위한 제약입니다.


### 문제 2

Clean Architecture에서 Use Case의 역할은?


   **A.** UI를 직접 제어

✅ **B.** 비즈니스 로직 실행 (Entity 사용)

   **C.** 네트워크 요청 직접 수행

   **D.** DB 쿼리 작성


**정답**: B


💡 **힌트**: Use Case는 \"이 앱이 무엇을 할 수 있는가\"를 표현하는 비즈니스 로직 단위입니다.


