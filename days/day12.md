# Day 12 — Combine 프레임워크

**태그**: Publisher · Subscriber · Backpressure · flatMap · combineLatest · AnyCancellable

---

## 📝 핵심 정리


### 1. Publisher / Subscriber 프로토콜

_아이콘: `blue`_


### Combine이란?

Apple이 iOS 13에서 도입한 **선언적 반응형 프로그래밍 프레임워크**입니다. 비동기 이벤트를 시간 순서대로 처리하는 파이프라인을 구성합니다.

### Publisher 프로토콜

값을 방출하는 주체입니다. 두 가지 Associated Type을 가집니다:

```swift
protocol Publisher {
    associatedtype Output    // 방출하는 값의 타입
    associatedtype Failure: Error  // 에러 타입 (Never면 에러 없음)
    
    func receive<S: Subscriber>(subscriber: S)
        where S.Input == Output, S.Failure == Failure
}
```

### Subscriber 프로토콜

Publisher가 방출한 값을 받는 주체입니다:

```swift
protocol Subscriber {
    associatedtype Input
    associatedtype Failure: Error
    
    func receive(subscription: Subscription)
    func receive(_ input: Input) -> Subscribers.Demand
    func receive(completion: Subscribers.Completion<Failure>)
}
```

### 구독 흐름 (Subscription Lifecycle)

```swift
// 1. Subscriber가 Publisher에 구독 요청
// 2. Publisher가 Subscription 객체를 Subscriber에게 전달
// 3. Subscriber가 Demand(요청량)를 Subscription에 전달
// 4. Publisher가 값을 방출 (Demand 범위 내에서)
// 5. 완료 또는 에러로 종료

let publisher = [1, 2, 3, 4, 5].publisher

let cancellable = publisher
    .map { $0 * 2 }
    .filter { $0 > 4 }
    .sink(
        receiveCompletion: { completion in
            print("완료: \\(completion)")
        },
        receiveValue: { value in
            print("값: \\(value)")  // 6, 8, 10
        }
    )
```

### 주요 내장 Publisher

```swift
// Just: 단일 값 방출 후 완료
let just = Just(42)

// Future: 비동기 작업 결과를 한 번 방출
let future = Future<String, Error> { promise in
    DispatchQueue.global().async {
        promise(.success("결과"))
    }
}

// @Published: 프로퍼티 래퍼로 값 변경 시 자동 방출
class ViewModel: ObservableObject {
    @Published var searchText = ""
    @Published var results: [Item] = []
}
```

> 💡 **💡 면접 포인트:** "Publisher는 값을 방출하는 프로토콜이고, Subscriber는 그 값을 받는 프로토콜입니다. 둘 사이에 Subscription이 중개 역할을 하며, Subscriber가 Demand를 통해 받을 수 있는 양을 제어합니다. 이것이 Backpressure의 기반입니다."


### 2. Backpressure와 Demand

_아이콘: `green`_


### Backpressure란?

Publisher가 Subscriber보다 빠르게 값을 방출할 때, **Subscriber가 처리할 수 있는 만큼만 요청**하는 메커니즘입니다. 메모리 폭발이나 데이터 유실을 방지합니다.

### Demand의 종류

```swift
// Subscribers.Demand
.none        // 추가 요청 없음 (0개)
.max(N)      // N개 추가 요청
.unlimited   // 무제한 (Backpressure 비활성화)
```

### Custom Subscriber로 Backpressure 구현

```swift
class ThrottledSubscriber: Subscriber {
    typealias Input = Int
    typealias Failure = Never
    
    func receive(subscription: Subscription) {
        // 처음에 3개만 요청
        subscription.request(.max(3))
    }
    
    func receive(_ input: Int) -> Subscribers.Demand {
        print("처리: \\(input)")
        // 하나 처리할 때마다 하나 더 요청
        return .max(1)
    }
    
    func receive(completion: Subscribers.Completion<Never>) {
        print("완료")
    }
}

let publisher = (1...100).publisher
publisher.subscribe(ThrottledSubscriber())
```

### 실무에서 Backpressure가 중요한 경우

```swift
// 검색 자동완성: 사용자 입력이 너무 빠를 때
$searchText
    .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
    .removeDuplicates()
    .flatMap { query in
        self.searchAPI(query)
    }
    .sink { results in
        self.results = results
    }
    .store(in: &cancellables)

// buffer: 값을 모아서 한번에 전달
publisher
    .buffer(size: 10, prefetch: .byRequest, whenFull: .dropOldest)
    .sink { ... }
```

> 💡 **💡 핵심:** sink와 assign은 내부적으로 `.unlimited` Demand를 사용합니다. 대부분의 UI 바인딩에서는 이것으로 충분하지만, 고빈도 데이터 스트림(센서, 웹소켓)에서는 buffer, throttle, debounce로 Backpressure를 관리해야 합니다.


### 3. AnyCancellable 메모리 관리

_아이콘: `orange`_


### AnyCancellable이란?

Combine 구독을 관리하는 토큰입니다. **deinit 시 자동으로 cancel()을 호출**하여 구독을 정리합니다.

### 메모리 관리 패턴

```swift
class UserViewModel: ObservableObject {
    @Published var users: [User] = []
    private var cancellables = Set<AnyCancellable>()
    
    func loadUsers() {
        apiService.fetchUsers()
            .receive(on: DispatchQueue.main)
            .sink(
                receiveCompletion: { [weak self] completion in
                    if case .failure(let error) = completion {
                        self?.handleError(error)
                    }
                },
                receiveValue: { [weak self] users in
                    self?.users = users
                }
            )
            .store(in: &cancellables)  // Set에 저장
    }
    // ViewModel deinit → cancellables deinit → 모든 구독 cancel
}
```

### 흔한 실수와 해결

```swift
// ❌ 실수 1: cancellable을 저장하지 않음
func loadData() {
    _ = publisher.sink { ... }  // 즉시 해제 → 구독 취소!
}

// ❌ 실수 2: 매번 새 구독을 추가만 함
func search(_ text: String) {
    // 이전 검색 구독이 계속 쌓임!
    makeRequest(text)
        .sink { ... }
        .store(in: &cancellables)
}

// ✅ 해결: 검색용 cancellable을 별도 관리
private var searchCancellable: AnyCancellable?

func search(_ text: String) {
    searchCancellable?.cancel()  // 이전 구독 취소
    searchCancellable = makeRequest(text)
        .sink { ... }
}
```

### assign(to:)의 메모리 함정

```swift
// ❌ assign(to:on:)은 self를 strong 캡처!
publisher
    .assign(to: \\.title, on: self)  // retain cycle 위험!
    .store(in: &cancellables)

// ✅ assign(to:)는 @Published에 직접 바인딩 (retain cycle 없음)
publisher
    .assign(to: &$title)  // AnyCancellable 반환 안 함, 자동 관리
```

> 💡 **💡 면접 답변:** "AnyCancellable은 구독의 생명주기를 관리하는 토큰입니다. Set<AnyCancellable>에 저장하면 소유자 해제 시 모든 구독이 자동 취소됩니다. assign(to:on:)은 strong 캡처로 순환 참조 위험이 있어, @Published 프로퍼티에는 assign(to: &$property)를 사용합니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. AnyCancellable을 Set에 저장하는 이유는? `[기본 / 빈출]`

**구독의 생명주기를 소유자에 바인딩하기 위해서입니다.**

AnyCancellable은 deinit 시 자동으로 cancel()을 호출합니다. Set<AnyCancellable>에 저장하면:
1. 소유자(ViewController 등)가 해제될 때 Set도 해제
2. Set 안의 모든 AnyCancellable이 deinit → cancel() 자동 호출
3. 모든 구독이 정리됨

만약 저장하지 않으면 sink가 반환하는 AnyCancellable이 즉시 해제되어 구독이 바로 취소됩니다.


### Q2. Combine과 async/await의 차이와 선택 기준은? `[심화 / 빈출]`

**핵심 차이: 값의 개수**

• async/await: 단일 값 반환 (1회성 비동기 작업)
• Combine: 시간에 따른 여러 값의 스트림

**선택 기준:**
• 네트워크 요청 1회 → async/await
• 실시간 검색, 타이머, 프로퍼티 변경 감지 → Combine
• UI 바인딩 (@Published) → Combine
• 여러 비동기 작업 조합 → 상황에 따라 (AsyncSequence도 가능)

iOS 15+에서는 AsyncSequence가 Combine의 일부 역할을 대체할 수 있지만, SwiftUI의 @Published 바인딩은 여전히 Combine 기반입니다.


### Q3. Subject와 Publisher의 차이는? `[기본 / 빈출]`

**Subject는 외부에서 값을 주입할 수 있는 Publisher입니다.**

일반 Publisher는 내부 로직에 의해서만 값이 방출됩니다. Subject는 `send(_:)` 메서드로 외부에서 값을 넣을 수 있죠.

두 가지 종류:
• **PassthroughSubject**: 현재 값 없음, 새 구독자는 이후 값만 받음
• **CurrentValueSubject**: 현재 값 보유, 새 구독자는 구독 즉시 현재 값 받음

실무에서는 imperative 코드(delegate, callback)를 reactive 스트림으로 브릿징할 때 주로 사용합니다.


### Q4. eraseToAnyPublisher()는 왜 필요한가요? `[기본]`

**타입 복잡도를 숨기기 위해서입니다.**

Combine 연산자를 체이닝하면 반환 타입이 중첩됩니다:
`Publishers.Map<Publishers.Filter<Publishers.Sequence<...>>, String>`

이걸 API 경계에서 노출하면 구현 변경 시 타입이 바뀌어 호출부가 깨집니다. eraseToAnyPublisher()로 `AnyPublisher<String, Error>`로 감싸면 내부 구현을 자유롭게 변경할 수 있습니다.


---


## ✏️ 퀴즈


### 문제 1

Combine에서 Backpressure를 제어하는 메커니즘은?


   **A.** Publisher가 속도를 조절한다

✅ **B.** Subscriber가 Demand로 요청량을 제어한다

   **C.** Scheduler가 자동으로 조절한다

   **D.** buffer가 항상 필요하다


**정답**: B


💡 **힌트**: Subscriber가 receive(_:)에서 반환하는 Demand 값으로 추가 요청량을 결정합니다.


### 문제 2

share() 연산자의 주요 목적은?


   **A.** Publisher를 캐싱한다

✅ **B.** 여러 Subscriber가 하나의 upstream 구독을 공유한다

   **C.** 에러를 공유한다

   **D.** 타입을 지운다


**정답**: B


💡 **힌트**: 비용이 큰 작업(네트워크 요청 등)을 중복 실행하지 않도록 합니다.


