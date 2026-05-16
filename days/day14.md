# Day 14 — Testing

**태그**: Unit Test · Mock · Protocol · async testing · Snapshot Test · XCTest

---

## 📝 핵심 정리


### 1. Unit Test with Mock/Protocol

_아이콘: `blue`_


### 왜 Mock이 필요한가요?

Unit Test는 **하나의 단위만 격리하여 테스트**해야 합니다. 네트워크, DB 같은 외부 의존성을 실제로 호출하면 느리고 불안정합니다. Mock으로 대체하면 빠르고 결정적인 테스트가 가능합니다.

### Protocol 기반 Mock 패턴

```swift
// 1. Protocol 정의
protocol UserRepositoryProtocol {
    func fetchUser(id: String) async throws -> User
    func saveUser(_ user: User) async throws
}

// 2. 실제 구현
class UserRepository: UserRepositoryProtocol {
    func fetchUser(id: String) async throws -> User {
        let data = try await networkService.request(.user(id: id))
        return try JSONDecoder().decode(User.self, from: data)
    }
    func saveUser(_ user: User) async throws { ... }
}

// 3. Mock 구현
class MockUserRepository: UserRepositoryProtocol {
    var fetchUserResult: Result<User, Error> = .success(User.stub())
    var fetchUserCallCount = 0
    var lastFetchedID: String?
    
    func fetchUser(id: String) async throws -> User {
        fetchUserCallCount += 1
        lastFetchedID = id
        return try fetchUserResult.get()
    }
    
    var saveUserCallCount = 0
    func saveUser(_ user: User) async throws {
        saveUserCallCount += 1
    }
}

// 4. ViewModel 테스트
class UserViewModelTests: XCTestCase {
    var sut: UserViewModel!
    var mockRepo: MockUserRepository!
    
    override func setUp() {
        mockRepo = MockUserRepository()
        sut = UserViewModel(repository: mockRepo)
    }
    
    func test_loadUser_성공시_user가_설정됨() async {
        // Given
        let expectedUser = User(id: "1", name: "철수")
        mockRepo.fetchUserResult = .success(expectedUser)
        
        // When
        await sut.loadUser(id: "1")
        
        // Then
        XCTAssertEqual(sut.user?.name, "철수")
        XCTAssertEqual(mockRepo.fetchUserCallCount, 1)
        XCTAssertEqual(mockRepo.lastFetchedID, "1")
    }
    
    func test_loadUser_실패시_에러상태() async {
        // Given
        mockRepo.fetchUserResult = .failure(NetworkError.notFound)
        
        // When
        await sut.loadUser(id: "999")
        
        // Then
        XCTAssertNil(sut.user)
        XCTAssertTrue(sut.showError)
    }
}
```

> 💡 **💡 면접 포인트:** "Protocol로 의존성을 추상화하고, 테스트에서는 Mock을 주입합니다. Mock에는 호출 횟수, 전달된 파라미터, 반환값을 제어할 수 있는 프로퍼티를 둡니다. 이렇게 하면 네트워크 없이도 모든 시나리오를 빠르게 검증할 수 있습니다."


### 2. Async Testing & XCTest 패턴

_아이콘: `green`_


### async/await 테스트

```swift
// Swift 5.5+: 테스트 메서드에 async 키워드 사용
func test_fetchData_async() async throws {
    // Given
    let service = MockDataService()
    service.result = .success([Item(id: 1)])
    
    // When
    let items = try await service.fetchItems()
    
    // Then
    XCTAssertEqual(items.count, 1)
}

// Combine Publisher 테스트
func test_publisher_emitsValues() {
    let expectation = expectation(description: "값 방출")
    var received: [Int] = []
    
    let publisher = [1, 2, 3].publisher
    publisher
        .sink(
            receiveCompletion: { _ in expectation.fulfill() },
            receiveValue: { received.append($0) }
        )
        .store(in: &cancellables)
    
    wait(for: [expectation], timeout: 1.0)
    XCTAssertEqual(received, [1, 2, 3])
}
```

### XCTest 주요 패턴

```swift
// Given-When-Then (AAA: Arrange-Act-Assert)
func test_패턴명_조건_기대결과() {
    // Given (준비)
    let calculator = Calculator()
    
    // When (실행)
    let result = calculator.add(2, 3)
    
    // Then (검증)
    XCTAssertEqual(result, 5)
}

// setUp / tearDown 생명주기
class MyTests: XCTestCase {
    override class func setUp() { }       // 클래스 전체에서 1번
    override func setUp() { }             // 각 테스트 메서드 전
    override func setUpWithError() throws { }  // 에러 throw 가능
    
    override func tearDown() { }          // 각 테스트 메서드 후
    override class func tearDown() { }    // 클래스 전체에서 1번
}

// XCTExpectation: 비동기 대기
func test_notification_received() {
    let exp = expectation(description: "알림 수신")
    
    NotificationCenter.default.addObserver(
        forName: .dataLoaded, object: nil, queue: nil
    ) { _ in
        exp.fulfill()
    }
    
    dataLoader.load()
    wait(for: [exp], timeout: 5.0)
}
```

### 테스트 더블 종류

- **Stub**: 미리 정해진 값을 반환 (행위 검증 X)

- **Mock**: 호출 여부/횟수/파라미터를 검증

- **Spy**: 실제 동작 + 호출 기록

- **Fake**: 간소화된 실제 구현 (InMemory DB 등)

> 💡 **💡 면접 답변:** "async 테스트는 메서드에 async throws를 붙여 자연스럽게 작성합니다. Combine은 expectation으로 비동기 완료를 기다립니다. 테스트는 Given-When-Then 구조로 가독성을 높이고, setUp에서 SUT와 Mock을 초기화하여 각 테스트의 독립성을 보장합니다."


### 3. Snapshot Testing

_아이콘: `purple`_


### Snapshot Testing이란?

UI 컴포넌트를 이미지로 렌더링하여 **이전에 저장된 참조 이미지와 픽셀 단위로 비교**하는 테스트 방식입니다. UI 회귀를 자동으로 감지합니다.

### swift-snapshot-testing 라이브러리 사용

```swift
import SnapshotTesting
import XCTest

class ProfileViewTests: XCTestCase {
    
    func test_profileView_기본상태() {
        let view = ProfileView(user: .stub())
        
        assertSnapshot(
            of: view,
            as: .image(layout: .device(config: .iPhone13))
        )
    }
    
    func test_profileView_다크모드() {
        let view = ProfileView(user: .stub())
        
        assertSnapshot(
            of: view,
            as: .image(
                layout: .device(config: .iPhone13),
                traits: UITraitCollection(userInterfaceStyle: .dark)
            )
        )
    }
    
    func test_profileView_긴_이름() {
        let user = User(name: "매우 긴 이름을 가진 사용자입니다 테스트")
        let view = ProfileView(user: user)
        
        assertSnapshot(
            of: view,
            as: .image(layout: .device(config: .iPhone13))
        )
    }
    
    // SwiftUI View 테스트
    func test_swiftUI_view() {
        let view = ContentView()
        let vc = UIHostingController(rootView: view)
        
        assertSnapshot(of: vc, as: .image(on: .iPhone13))
    }
}
```

### Snapshot Testing 전략

```swift
// 여러 디바이스/상태 한번에 테스트
func test_loginButton_allStates() {
    let states: [(String, LoginButton.State)] = [
        ("normal", .normal),
        ("loading", .loading),
        ("disabled", .disabled),
        ("error", .error("잘못된 비밀번호"))
    ]
    
    for (name, state) in states {
        let button = LoginButton(state: state)
        assertSnapshot(
            of: button,
            as: .image,
            named: name  // 각 상태별 별도 참조 이미지
        )
    }
}

// 참조 이미지 업데이트 (UI 변경 시)
// record: true로 설정하면 새 참조 이미지 생성
assertSnapshot(of: view, as: .image, record: true)
```

> 💡 **💡 면접 답변:** "Snapshot Testing은 UI 회귀를 자동 감지합니다. PR에서 스냅샷 차이가 발생하면 의도된 변경인지 리뷰합니다. 다크모드, 다양한 디바이스, 접근성 폰트 크기 등 여러 조건을 조합하여 테스트합니다. 단, CI 환경과 로컬의 렌더링 차이에 주의해야 합니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. 테스트 커버리지 100%가 좋은 목표인가요? `[기본 / 빈출]`

**아닙니다. 의미 있는 커버리지가 중요합니다.**

100% 커버리지를 목표로 하면 getter/setter 같은 trivial 코드까지 테스트하게 되어 유지보수 비용만 증가합니다.

실무 기준:
• 비즈니스 로직 (ViewModel, UseCase): 80%+ 목표
• UI 레이어: Snapshot Test로 주요 상태 커버
• 유틸리티/헬퍼: 엣지 케이스 위주
• 네트워킹 레이어: Integration Test로 별도 관리

핵심은 '변경 시 깨져야 할 테스트가 깨지는가'입니다.


### Q2. XCTest에서 비동기 테스트 방법은? `[기본 / 빈출]`

**세 가지 방법이 있습니다:**

1. **async/await** (권장): 테스트 메서드에 async 키워드
`func test_example() async throws { }`

2. **XCTestExpectation**: fulfill()과 wait(for:timeout:)
콜백 기반 API 테스트에 적합

3. **Combine + expectation**: Publisher의 완료를 기다림

iOS 16+에서는 async가 가장 깔끔합니다. 레거시 콜백 API는 expectation을 사용합니다.


### Q3. Mock과 Stub의 차이는? `[심화 / 빈출]`

**검증 대상이 다릅니다.**

• **Stub**: 상태 검증 (State Verification). 미리 정해진 값을 반환하고, 테스트는 SUT의 최종 상태를 검증
• **Mock**: 행위 검증 (Behavior Verification). 특정 메서드가 호출되었는지, 몇 번 호출되었는지, 어떤 파라미터로 호출되었는지를 검증

예시:
• Stub: mockRepo.fetchResult = .success(user) → sut.user == user 검증
• Mock: verify(mockRepo.save was called once with user) → 호출 자체를 검증


### Q4. 테스트 피라미드에서 각 레벨의 비율은? `[기본]`

**Unit > Integration > UI (E2E)**

• Unit Test (70%): 빠르고 격리됨. 비즈니스 로직 중심
• Integration Test (20%): 모듈 간 상호작용. API 계약 검증
• UI/E2E Test (10%): 느리고 불안정. 핵심 사용자 플로우만

iOS에서는:
• Unit: XCTest + Mock
• Integration: 실제 네트워크/DB 포함 테스트
• UI: XCUITest (최소한으로)


---


## ✏️ 퀴즈


### 문제 1

Protocol 기반 Mock 패턴의 주요 장점은?


   **A.** 코드량이 줄어든다

✅ **B.** 컴파일 타임에 의존성 검증이 가능하다

   **C.** 런타임 성능이 향상된다

   **D.** 상속이 필요 없다


**정답**: B


💡 **힌트**: Protocol을 통해 의존성 타입이 컴파일 시점에 확인되어 안전합니다.


### 문제 2

Snapshot Testing에서 record: true의 역할은?


   **A.** 테스트를 기록한다

✅ **B.** 새로운 참조 이미지를 생성한다

   **C.** 테스트 결과를 파일로 저장한다

   **D.** 성능을 측정한다


**정답**: B


💡 **힌트**: UI가 의도적으로 변경되었을 때 새 기준 이미지를 만드는 데 사용합니다.


