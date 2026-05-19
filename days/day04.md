# Day 4 — Concurrency: GCD와 Swift Concurrency

**태그**: GCD · DispatchQueue · DispatchGroup · DispatchWorkItem · async/await · Task · Actor · Sendable · MainActor

---

## 📝 핵심 정리

## 1. GCD: Queue, Thread, sync/async

### GCD가 뭔가요?

GCD(Grand Central Dispatch)는 Apple이 제공하는 동시성 API입니다. 개발자가 직접 Thread를 만들고 관리하는 대신, **Queue에 작업을 넣으면 시스템이 적절한 Thread에서 실행**해줍니다.

핵심은 이겁니다.

```text
Thread = 실제로 코드가 실행되는 실행 단위
Queue  = 실행할 작업을 담고, 순서와 동시성 정책을 관리하는 추상화
```

즉, Queue와 Thread는 같은 개념이 아닙니다. 개발자는 Queue에 작업을 넣고, 실제 어떤 Thread에서 실행할지는 GCD가 시스템 상태에 따라 결정합니다.

```swift
DispatchQueue.global().async {
    print("작업 실행")
}
```

위 코드에서 우리는 global queue에 작업을 넣을 뿐이고, 실제 Thread 배정은 GCD가 합니다.

### Serial Queue vs Concurrent Queue

Serial/Concurrent는 **Queue의 실행 정책**입니다.

| 구분 | 의미 |
|---|---|
| Serial Queue | 한 번에 하나씩, 들어온 순서대로 작업 실행 |
| Concurrent Queue | 여러 작업을 동시에 실행할 수 있음 |

```swift
let serial = DispatchQueue(label: "com.app.serial")

serial.async { print("A") }
serial.async { print("B") }
serial.async { print("C") }

// A → B → C 순서로 실행
```

Serial Queue는 **큐에 들어온 block 자체의 실행 순서**를 보장합니다. 다만 block 내부에서 다시 비동기 작업을 시작하면, 그 비동기 작업의 완료 순서까지 보장하지는 않습니다.

```swift
let serial = DispatchQueue(label: "com.app.serial")

serial.async {
    URLSession.shared.dataTask(with: urlA) { _, _, _ in
        print("A 완료")
    }.resume()
}

serial.async {
    URLSession.shared.dataTask(with: urlB) { _, _, _ in
        print("B 완료")
    }.resume()
}
```

이 경우 A 요청을 시작한 뒤 B 요청을 시작하는 순서는 보장됩니다. 하지만 네트워크 응답은 B가 먼저 올 수도 있습니다.

Concurrent Queue는 여러 작업의 동시 실행을 **허용**하지만, 모든 작업이 반드시 동시에 실행된다는 뜻은 아닙니다. 실제 실행 시점과 Thread 배정은 CPU 코어 수, 시스템 부하, QoS 등에 따라 달라집니다.

```swift
let concurrent = DispatchQueue(label: "com.app.concurrent", attributes: .concurrent)

concurrent.async { print("A") }
concurrent.async { print("B") }
concurrent.async { print("C") }

// 출력 순서 보장 안 됨
```

### sync vs async

sync/async는 **호출자가 작업 완료를 기다리는지 여부**입니다.

| 구분 | 의미 |
|---|---|
| `sync` | Queue에 넣은 작업이 끝날 때까지 현재 실행 흐름을 block |
| `async` | Queue에 작업을 예약하고, 완료를 기다리지 않고 다음 코드 실행 |

```swift
print("A")
DispatchQueue.global().sync {
    print("B")
}
print("C")
// A → B → C
```

```swift
print("A")
DispatchQueue.global().async {
    print("B")
}
print("C")
// 보통 A → C → B
```

중요한 점은 이것입니다.

```text
Serial/Concurrent = Queue가 작업을 어떻게 실행할지
sync/async        = 호출자가 작업 완료를 기다릴지
```

따라서 `serial.async`는 비동기지만 Serial Queue이므로 작업은 하나씩 순서대로 실행됩니다.

### DispatchQueue.main.async를 자주 쓰는 이유

UIKit, SwiftUI의 UI 업데이트는 Main Thread에서 해야 합니다. 그래서 네트워크 요청, 이미지 디코딩, 파일 처리 같은 작업은 background에서 처리하고, 결과를 화면에 반영할 때 Main Queue로 돌아옵니다.

```swift
DispatchQueue.global(qos: .userInitiated).async {
    let image = decodeImage(data)

    DispatchQueue.main.async {
        self.imageView.image = image
    }
}
```

`DispatchQueue.main.async`는 Main Queue에 작업을 예약할 뿐, 항상 즉시 실행되는 것은 아닙니다. Main Queue는 Serial Queue이기 때문에 현재 실행 중인 작업과 앞에 쌓인 작업이 끝난 뒤 실행됩니다.

### ⚠️ Main Thread에서 main.sync를 호출하면?

Main Thread에서 `DispatchQueue.main.sync`를 호출하면 deadlock이 발생합니다.

```swift
// 이미 Main Thread에서 실행 중이라고 가정
DispatchQueue.main.sync {
    print("UI Update")
}
```

흐름은 이렇습니다.

```text
Main Thread:
main.sync 블록이 끝날 때까지 기다림

Main Queue:
sync 블록을 실행하려면 Main Thread가 비어야 함

결과:
서로 기다리면서 deadlock
```

`main.async`는 작업을 예약하고 현재 흐름을 막지 않기 때문에 이런 deadlock을 피할 수 있습니다.

### DispatchGroup: 여러 작업이 모두 끝난 뒤 처리

`DispatchGroup`은 여러 비동기 작업을 동시에 실행하고, **모든 작업이 끝난 뒤 후처리**를 하고 싶을 때 사용합니다.

```swift
let group = DispatchGroup()

var user: User?
var posts: [Post]?
var comments: [Comment]?

group.enter()
api.fetchUser { result in
    defer { group.leave() }
    user = try? result.get()
}

group.enter()
api.fetchPosts { result in
    defer { group.leave() }
    posts = try? result.get()
}

group.enter()
api.fetchComments { result in
    defer { group.leave() }
    comments = try? result.get()
}

group.notify(queue: .main) {
    self.updateUI(user: user, posts: posts, comments: comments)
}
```

```text
enter() = 작업 시작 카운트 +1
leave() = 작업 완료 카운트 -1
notify() = 카운트가 0이 되면 실행
```

`enter()`와 `leave()` 개수가 맞지 않으면 `notify`가 영원히 호출되지 않거나, 반대로 `leave()`가 더 많으면 크래시가 발생할 수 있습니다. 그래서 콜백 내부에서는 `defer { group.leave() }`를 자주 사용합니다.

### DispatchWorkItem: 작업을 객체처럼 다루기

`DispatchWorkItem`은 GCD에 넣을 작업 block을 객체처럼 보관하고 싶을 때 사용합니다. 대표적으로 작업 취소 요청, 완료 후 notify, debounce 구현에 사용됩니다.

```swift
let workItem = DispatchWorkItem {
    print("무거운 작업")
}

workItem.notify(queue: .main) {
    print("작업 완료 후 UI 업데이트")
}

DispatchQueue.global().async(execute: workItem)
```

검색어 입력 debounce 예시는 다음과 같습니다.

```swift
var searchWorkItem: DispatchWorkItem?

func searchTextDidChange(_ text: String) {
    searchWorkItem?.cancel()

    let workItem = DispatchWorkItem { [weak self] in
        self?.requestSearchAPI(text)
    }

    searchWorkItem = workItem
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5, execute: workItem)
}
```

GCD의 `cancel()`은 이미 실행 중인 작업을 강제로 멈추지 않습니다. 취소 상태를 표시할 뿐이고, 작업 내부에서 직접 `isCancelled`를 확인해야 합니다.

> 면접 포인트: GCD에서 Queue는 작업을 담는 추상화이고 Thread는 실제 실행 단위입니다. Serial/Concurrent는 Queue의 실행 정책, sync/async는 호출자가 기다리는지 여부입니다. UI 업데이트는 Main Queue에서 해야 하며, Main Thread에서 `main.sync`를 호출하면 deadlock이 발생합니다.

---

## 2. QoS, Thread Explosion, 네트워크 작업의 오해

### QoS는 우선순위 명령이 아니라 힌트

QoS(Quality of Service)는 작업의 중요도와 긴급도를 시스템에 알려주는 힌트입니다. 시스템은 이를 참고해 CPU, 스레드 스케줄링, 에너지 사용을 조절합니다.

| QoS | 기준 | 예시 |
|---|---|---|
| `.userInteractive` | 사용자의 즉각적인 반응에 필요 | 터치 반응, 애니메이션 |
| `.userInitiated` | 사용자가 결과를 기다림 | 버튼 탭 후 화면 로딩, 검색 결과 로딩 |
| `.utility` | 시간이 걸려도 되지만 완료가 필요 | 파일 다운로드, 데이터 동기화 |
| `.background` | 사용자에게 당장 보이지 않음 | 로그 업로드, 캐시 정리 |
| `.default` | 명시하지 않은 기본값 | 일반 작업 |

무조건 높은 QoS를 준다고 앱이 빨라지는 것은 아닙니다. 캐시 정리나 로그 업로드를 `userInteractive`로 실행하면 실제 UI 작업과 리소스를 경쟁하게 되어 오히려 반응성이 떨어질 수 있습니다.

```swift
DispatchQueue.global(qos: .userInitiated).async {
    let data = fetchData()

    DispatchQueue.main.async {
        self.show(data)
    }
}
```

### Thread Explosion이란?

Thread Explosion은 동시에 처리하려는 작업이 많아지면서 시스템이 많은 Thread를 만들거나 깨우게 되고, 그 결과 메모리 사용량 증가, context switching 증가, CPU 경쟁, 성능 저하가 발생하는 현상입니다.

특히 문제가 되는 것은 **blocking 작업**입니다.

```swift
let semaphore = DispatchSemaphore(value: 0)

for _ in 0..<1000 {
    DispatchQueue.global().async {
        semaphore.wait()   // 현재 Thread를 block
        doWork()
        semaphore.signal()
    }
}
```

이런 코드에서는 Thread가 `wait()`에서 막힌 채 반환되지 않습니다. GCD는 처리량을 유지하려고 추가 Thread를 만들 수 있고, 그 작업들도 다시 block되면 Thread 수가 과도하게 늘어납니다.

주의해야 하는 blocking 호출은 다음과 같습니다.

```text
semaphore.wait()
DispatchGroup.wait()
NSLock.lock() 후 오래 대기
queue.sync 중첩 호출
동기 네트워크/파일 작업
```

해결 방향은 다음과 같습니다.

```swift
// OperationQueue로 동시 실행 수 제한
let queue = OperationQueue()
queue.maxConcurrentOperationCount = 4

// Swift Concurrency에서는 TaskGroup 사용 후 필요 시 동시성 제한 설계
```

### 네트워크 요청은 DispatchQueue.global().async로 감싸야 할까?

일반적으로 Moya나 Alamofire 네트워킹을 직접 `DispatchQueue.global().async`로 감쌀 필요는 없습니다.

```text
Moya
 ↓
Alamofire
 ↓
URLSession
 ↓
iOS networking system
```

실제 네트워크 I/O는 `URLSession`과 시스템 네트워크 레이어가 비동기로 처리합니다. `DispatchQueue`는 네트워크 통신 자체를 수행하기보다는, 응답 콜백이나 데이터 가공을 어느 Queue에서 실행할지 제어하는 데 사용됩니다.

RxMoya를 사용한다면 `zip`도 Thread를 직접 만드는 도구가 아닙니다.

```swift
Single.zip(
    provider.rx.request(.user),
    provider.rx.request(.posts),
    provider.rx.request(.comments)
)
.observe(on: MainScheduler.instance)
.subscribe(onSuccess: { user, posts, comments in
    self.updateUI()
})
.disposed(by: disposeBag)
```

`zip`은 여러 Single을 구독하고, 각 결과가 모두 준비되면 묶어서 방출하는 조합 연산자입니다. 병렬성은 `zip`이 Thread를 만들어서 생기는 것이 아니라, 각 네트워크 요청이 `URLSession` 기반 비동기 작업으로 동시에 시작되기 때문에 생깁니다.

UI 업데이트가 있다면 `observe(on: MainScheduler.instance)` 또는 MainActor로 명확히 전환해야 합니다.

> 면접 포인트: QoS는 "무조건 빨리 실행해줘"가 아니라 "이 작업이 사용자 경험상 얼마나 중요한지"를 알려주는 힌트입니다. Thread Explosion은 작업이 많아서가 아니라, 많은 작업이 Thread를 block한 채 반환하지 않을 때 주로 발생합니다. 네트워크 요청 자체는 URLSession이 비동기로 처리하므로 global queue로 감싸는 것이 본질적인 병렬 처리 방법은 아닙니다.

---

## 3. Swift Concurrency: async/await, Task, TaskGroup

### async/await가 해결하는 문제

기존 completion handler 방식은 비동기 흐름이 깊어질수록 코드가 복잡해지고, 에러 처리와 취소 처리가 흩어지기 쉽습니다.

```swift
func loadProfile(id: String, completion: @escaping (Result<User, Error>) -> Void) {
    fetchUser(id: id) { userResult in
        switch userResult {
        case .success(let user):
            fetchPosts(userId: user.id) { postsResult in
                // 중첩 증가
            }
        case .failure(let error):
            completion(.failure(error))
        }
    }
}
```

`async/await`는 비동기 코드를 동기 코드처럼 읽히게 만듭니다.

```swift
func loadProfile(id: String) async throws -> UserProfile {
    let user = try await fetchUser(id: id)
    let posts = try await fetchPosts(userId: user.id)
    return UserProfile(user: user, posts: posts)
}
```

### await는 Thread를 block하지 않는다

`await`는 "결과를 기다린다"는 의미지만, GCD의 `sync`나 semaphore의 `wait()`처럼 Thread를 붙잡고 기다리지 않습니다.

```text
await 지점 도달
→ 현재 Task가 suspension
→ Thread는 다른 작업을 실행할 수 있음
→ 비동기 작업 완료 후 Task가 재개
```

```swift
func fetchData() async throws -> Data {
    let (data, _) = try await URLSession.shared.data(from: url)
    return data
}
```

여기서 네트워크 응답을 기다리는 동안 현재 Thread는 반환될 수 있습니다. 이 점이 blocking 기반 GCD 코드와 큰 차이입니다.

### Task는 Thread가 아니다

`Task`는 Swift Concurrency에서 비동기 작업을 표현하는 단위입니다. Thread는 실제 실행 자원이고, Task는 런타임이 스케줄링하는 작업입니다.

```swift
Task {
    let user = try await fetchUser()
    print(user)
}
```

```text
Task   = 비동기 작업 단위
Thread = 실제 코드 실행 단위
```

`await` 전과 후가 항상 같은 Thread에서 실행된다고 보장할 수 없습니다.

### Task와 Task.detached

`Task {}`는 현재 context를 어느 정도 상속합니다. 예를 들어 `@MainActor` 안에서 생성된 `Task`는 MainActor context를 상속할 수 있습니다.

```swift
@MainActor
func userTapped() {
    Task {
        self.isLoading = true
        await loadData()
        self.isLoading = false
    }
}
```

`Task.detached {}`는 현재 actor context와 분리된 독립 작업입니다. 그래서 UI 상태나 actor-isolated 상태에 접근할 때 더 조심해야 합니다.

```swift
@MainActor
func userTapped() {
    Task.detached {
        let result = await heavyWork()

        await MainActor.run {
            self.show(result)
        }
    }
}
```

일반적으로는 `Task {}`를 우선 사용하고, 현재 actor context와 완전히 분리해야 하는 명확한 이유가 있을 때만 `Task.detached`를 사용합니다.

### 순차 실행, 병렬 실행, 결과 순서

서로 의존성이 있는 작업은 순차 실행이 맞습니다.

```swift
let user = try await fetchUser()
let posts = try await fetchPosts(userId: user.id)
```

서로 독립적인 작업은 `async let`으로 병렬 실행할 수 있습니다.

```swift
async let profile = fetchProfile()
async let banners = fetchBanners()
async let products = fetchProducts()

let screenData = try await ScreenData(
    profile: profile,
    banners: banners,
    products: products
)
```

`async let`은 작업 개수가 고정되어 있을 때 적합합니다.

작업 개수가 런타임에 결정되면 `TaskGroup`이 적합합니다.

```swift
func downloadImages(urls: [URL]) async throws -> [UIImage] {
    try await withThrowingTaskGroup(of: (Int, UIImage).self) { group in
        for (index, url) in urls.enumerated() {
            group.addTask {
                let image = try await downloadImage(from: url)
                return (index, image)
            }
        }

        var result = Array<UIImage?>(repeating: nil, count: urls.count)

        for try await (index, image) in group {
            result[index] = image
        }

        return result.compactMap { $0 }
    }
}
```

TaskGroup에서 중요한 점은 다음입니다.

```text
addTask 순서     = 작업을 추가한 순서
실제 실행 순서   = 보장 안 됨
결과 수신 순서   = 완료된 순서
원래 순서 필요   = index를 같이 반환해서 재정렬
```

여러 `Task {}`를 순서대로 만들었다고 해서 첫 번째 Task가 반드시 먼저 실행되거나 actor에 먼저 도착한다고 보장할 수 없습니다. 순서를 보장하려면 같은 Task 안에서 `await`를 순차적으로 호출해야 합니다.

```swift
let value = await counter.get()
await counter.increase()
```

### Swift Concurrency의 취소

Swift Concurrency의 취소도 협력적 취소입니다.

```swift
let task = Task {
    try await loadData()
}

task.cancel()
```

`cancel()`을 호출한다고 이미 실행 중인 작업이 즉시 강제 종료되지는 않습니다. 작업 내부에서 취소 여부를 확인해야 합니다.

```swift
func heavyWork() async throws {
    for item in items {
        try Task.checkCancellation()
        try await process(item)
    }
}
```

```swift
if Task.isCancelled {
    return
}
```

| API | 의미 |
|---|---|
| `Task.checkCancellation()` | 취소 상태면 `CancellationError` throw |
| `Task.isCancelled` | 취소 여부를 Bool로 확인 |

> 면접 포인트: `await`는 Thread를 block하는 것이 아니라 Task를 suspension하는 지점입니다. `Task`는 Thread가 아니며, `async let`은 고정 개수 병렬 작업, `TaskGroup`은 동적 개수 병렬 작업에 적합합니다. 여러 Task의 실행 순서와 완료 순서는 보장되지 않으므로, 순서가 중요하면 같은 Task 안에서 순차 호출하거나 index로 재정렬해야 합니다.

---

## 4. Actor, @MainActor, Sendable

### Actor가 해결하는 문제

Actor는 내부 mutable state를 동시 접근으로부터 보호하는 참조 타입입니다. 기존에 Serial Queue나 Lock으로 보호하던 공유 상태를 Swift Concurrency의 actor isolation으로 표현할 수 있습니다.

```swift
final class UnsafeCounter {
    var value = 0

    func increase() {
        value += 1
    }
}
```

위 class는 여러 Thread/Task에서 동시에 접근하면 data race가 생길 수 있습니다.

```swift
actor Counter {
    private var value = 0

    func increase() {
        value += 1
    }

    func get() -> Int {
        value
    }
}
```

외부에서 actor-isolated state에 접근하려면 `await`가 필요합니다.

```swift
let counter = Counter()

Task {
    await counter.increase()
    let value = await counter.get()
}
```

여기서 `await`는 동일 Thread에 접근하기 위한 것이 아닙니다.

```text
await counter.get()
= Counter actor가 보호하는 상태를 안전하게 읽을 차례를 기다림
= Thread를 block하는 것이 아니라 현재 Task가 suspension됨
```

Actor는 내부 상태 접근을 한 번에 하나씩 처리합니다. 하지만 여러 Task 중 어떤 요청이 먼저 actor에 도착할지는 스케줄러에 따라 달라질 수 있습니다.

### Actor 프로퍼티 접근

actor의 저장 프로퍼티 접근은 불변인지 가변인지에 따라 다릅니다.

```swift
actor UserStore {
    let id: Int = 1
    private var name: String = "min"

    func currentName() -> String {
        name
    }
}
```

```swift
let store = UserStore()

print(store.id)                       // let은 외부에서 바로 읽을 수 있음
let name = await store.currentName()  // var는 actor 순서를 거쳐야 함
```

정리하면 다음과 같습니다.

```text
let 저장 프로퍼티 read → 보통 바로 가능
var 저장 프로퍼티 read → actor-isolated라 await 필요
var 저장 프로퍼티 write → 외부 직접 변경 불가, actor 메서드로 변경
```

### Actor Reentrancy: data race는 막지만 로직 race는 남는다

Actor는 내부 상태의 data race를 막아줍니다. 하지만 actor 메서드 내부에서 `await`를 만나면 해당 작업이 suspension되고, 그 사이 actor가 다른 작업을 처리할 수 있습니다.

예를 들어 토큰 매니저를 보겠습니다.

```swift
actor TokenManager {
    private var token: String?

    func getToken() async throws -> String {
        if let token {
            return token
        }

        let newToken = try await requestNewToken()
        self.token = newToken
        return newToken
    }
}
```

동시에 두 Task가 호출하면 다음 흐름이 가능합니다.

```text
Task A: token nil 확인
Task A: requestNewToken() await로 일시 중단

그 사이

Task B: token nil 확인
Task B: requestNewToken() 호출

결과:
토큰 갱신 API가 두 번 호출될 수 있음
```

Actor가 `token`의 data race는 막았지만, "토큰 갱신은 한 번만 해야 한다"는 비즈니스 로직까지 자동으로 보장하지는 못한 것입니다.

해결하려면 `await` 전에 다른 호출자가 볼 수 있는 상태를 먼저 남겨야 합니다.

```swift
actor TokenManager {
    private var token: String?
    private var refreshTask: Task<String, Error>?

    func getToken() async throws -> String {
        if let token {
            return token
        }

        if let refreshTask {
            return try await refreshTask.value
        }

        let task = Task {
            try await requestNewToken()
        }

        refreshTask = task

        do {
            let newToken = try await task.value
            token = newToken
            refreshTask = nil
            return newToken
        } catch {
            refreshTask = nil
            throw error
        }
    }
}
```

핵심은 이것입니다.

```text
Actor는 메모리 안전성은 도와주지만,
await 전후의 비즈니스 로직 전체를 원자적으로 보장하지는 않는다.
```

### @MainActor와 MainThread의 관계

`@MainActor`와 Main Thread는 강하게 연결되어 있지만 완전히 같은 개념은 아닙니다.

```text
MainThread = 실제 UI 작업이 실행되는 OS Thread
MainActor  = Swift Concurrency에서 UI 관련 상태 접근을 직렬화하는 Global Actor
@MainActor = 이 코드/상태를 MainActor에 격리하겠다는 선언
```

Apple 플랫폼에서 MainActor는 일반적으로 Main Thread와 연결되어 있어 UI 업데이트에 사용됩니다.

```swift
@MainActor
final class ViewModel {
    private(set) var state: State = .idle

    func updateState(_ state: State) {
        self.state = state
    }
}
```

`DispatchQueue.main.async`는 런타임에 Main Queue로 작업을 예약하는 방식입니다. 반면 `@MainActor`는 Swift Concurrency의 타입 시스템이 actor isolation을 검사해주는 선언적 방식입니다.

```swift
// GCD 방식
DispatchQueue.main.async {
    self.label.text = "완료"
}

// Swift Concurrency 방식
await MainActor.run {
    self.label.text = "완료"
}
```

주의할 점은 `@MainActor` 안에서 무거운 작업을 하면 UI가 버벅일 수 있다는 것입니다. ViewModel 전체에 `@MainActor`를 붙이면 UI 상태 변경은 안전해지지만, 무거운 파싱이나 계산까지 MainActor에서 실행되지 않도록 분리해야 합니다.

```swift
func load() async {
    let model = await repository.fetchAndParse()

    await MainActor.run {
        self.state = .loaded(model)
    }
}
```

### Sendable이란?

`Sendable`은 쉽게 말해 **다른 비동기 작업으로 넘겨도 안전한 타입인지 표시하는 약속**입니다.

어렵게 말하는 "동시성 경계"는 다음처럼 이해하면 됩니다.

```text
동시성 경계를 넘는다
= 어떤 값이 다른 Task나 Actor로 전달된다
= 동시에 실행될 수 있는 다른 실행 흐름으로 값이 넘어간다
```

예를 들어 `Task` 내부로 값을 넘기는 것도 동시성 경계를 넘는 상황입니다.

```swift
let user = User(id: 1, name: "min")

Task {
    print(user)
}
```

값 타입이고 내부 프로퍼티가 모두 안전하면 `Sendable`로 다루기 쉽습니다.

```swift
struct UserResponse: Decodable, Sendable {
    let id: Int
    let name: String
}
```

반면 mutable class는 여러 Task에서 같은 인스턴스를 동시에 변경할 수 있어 위험합니다.

```swift
final class UserSession {
    var token: String = ""
}

let session = UserSession()

Task { session.token = "A" }
Task { session.token = "B" }
```

struct라도 내부에 mutable class를 들고 있으면 안전하지 않을 수 있습니다.

```swift
final class Profile {
    var nickname: String = ""
}

struct User {
    let id: Int
    let profile: Profile
}
```

즉, struct라서 무조건 Sendable인 것이 아니라 **안에 들어있는 값까지 모두 안전해야 Sendable**입니다.

actor는 기본적으로 Sendable로 취급됩니다. actor는 참조 타입이지만 내부 mutable state 접근이 actor isolation으로 보호되기 때문입니다.

다만 actor 내부의 mutable reference type을 외부로 그대로 반환하면 actor 보호 밖으로 빠져나가기 때문에 조심해야 합니다.

```swift
final class Session {
    var token: String = ""
}

actor SessionStore {
    private var session = Session()

    func currentSession() -> Session {
        session // 위험: actor 밖에서 같은 참조를 동시에 수정할 수 있음
    }
}
```

더 안전한 방식은 Sendable한 값 타입 snapshot을 반환하는 것입니다.

```swift
struct SessionSnapshot: Sendable {
    let token: String
}

actor SessionStore {
    private var token = ""

    func currentSession() -> SessionSnapshot {
        SessionSnapshot(token: token)
    }
}
```

`@unchecked Sendable`은 컴파일러가 안전성을 확인하지 못하지만, 개발자가 lock 등으로 직접 thread-safety를 보장하겠다고 선언하는 것입니다.

```swift
final class SafeCounter: @unchecked Sendable {
    private var value = 0
    private let lock = NSLock()

    func increase() {
        lock.lock()
        defer { lock.unlock() }
        value += 1
    }
}
```

잘못 사용하면 컴파일러가 data race를 막아주지 못하므로 정말 필요한 경우에만 사용해야 합니다.

> 면접 포인트: Actor는 내부 mutable state 접근을 직렬화해 data race를 막습니다. 하지만 actor 메서드 안의 `await` 지점에서는 reentrancy가 발생할 수 있어 로직 race는 별도로 설계해야 합니다. `Sendable`은 여러 비동기 작업으로 값을 넘겨도 안전하다고 말할 수 있는 타입이며, actor는 기본적으로 Sendable이지만 actor 밖으로 mutable reference를 그대로 내보내면 위험합니다.

---

## 💬 꼬리 질문 & 면접 답변

### Q1. GCD에서 Queue와 Thread는 같은 개념인가요?

아닙니다. Thread는 실제로 작업이 실행되는 실행 단위이고, Queue는 실행할 작업을 담고 순서와 동시성 정책을 관리하는 추상화입니다. 개발자는 Queue에 작업을 넣고, 실제 어떤 Thread에서 실행할지는 GCD가 관리합니다.

---

### Q2. Serial Queue와 Concurrent Queue의 차이는 무엇인가요?

Serial Queue는 큐에 들어온 작업을 한 번에 하나씩 순서대로 실행합니다. Concurrent Queue는 여러 작업을 동시에 실행할 수 있습니다. 다만 concurrent라고 해서 모든 작업이 반드시 동시에 실행되는 것은 아니고, 실제 병렬 실행 여부는 GCD가 시스템 상태를 보고 결정합니다.

---

### Q3. sync와 async의 차이는 무엇인가요?

`sync`는 작업을 Queue에 넣고 완료될 때까지 현재 실행 흐름을 block합니다. `async`는 작업을 Queue에 예약하고 완료를 기다리지 않고 바로 다음 코드로 넘어갑니다. 즉, 핵심 차이는 실행 순서가 아니라 호출자가 기다리는지 여부입니다.

---

### Q4. DispatchQueue.main.sync를 Main Thread에서 호출하면 어떻게 되나요?

deadlock이 발생합니다. Main Thread는 `main.sync` 블록이 끝나길 기다리지만, 그 블록도 Main Queue에서 실행되어야 하므로 Main Thread가 비어야 합니다. 서로 기다리게 되어 앱이 멈춥니다.

---

### Q5. DispatchGroup은 언제 사용하나요?

여러 비동기 작업을 동시에 실행하고, 모든 작업이 끝난 뒤 하나의 후처리를 해야 할 때 사용합니다. 각 작업 시작 전에 `enter()`, 완료 시점에 `leave()`를 호출하고, 모든 작업이 끝나면 `notify(queue:)`가 실행됩니다.

---

### Q6. DispatchWorkItem.cancel()을 호출하면 이미 실행 중인 작업도 즉시 멈추나요?

아닙니다. GCD의 취소는 강제 중단이 아니라 협력적 취소입니다. `cancel()`은 취소 상태를 표시할 뿐이고, 이미 실행 중인 작업은 내부에서 취소 여부를 직접 확인하고 return해야 멈출 수 있습니다.

---

### Q7. GCD에서 Thread Explosion은 왜 일어나나요?

global concurrent queue에 많은 작업을 넣고, 각 작업이 semaphore, lock, sync, wait 등으로 Thread를 block하면 GCD는 처리량을 유지하기 위해 추가 Thread를 만들 수 있습니다. 이 작업들도 다시 block되면 Thread 수가 과도하게 늘어나 성능 저하와 메모리 증가가 발생합니다.

---

### Q8. Moya나 Alamofire 요청을 DispatchQueue.global().async로 감싸야 하나요?

일반적으로 필요 없습니다. Moya는 Alamofire를 사용하고 Alamofire는 URLSession 기반으로 동작합니다. 실제 네트워크 I/O는 URLSession이 비동기로 처리합니다. DispatchQueue는 요청 자체보다 응답 콜백, 파싱, UI 업데이트 위치를 제어할 때 사용합니다.

---

### Q9. RxSwift zip은 Thread를 직접 관리하나요?

아닙니다. `zip`은 여러 Observable 또는 Single의 이벤트를 모아 같은 순번의 값이 모두 준비되면 묶어서 방출하는 조합 연산자입니다. Thread를 만들거나 병렬 실행을 직접 관리하지 않습니다. RxMoya에서 병렬 요청처럼 보이는 이유는 여러 request가 동시에 구독되고 URLSession이 비동기로 처리하기 때문입니다.

---

### Q10. await를 만나면 현재 Thread가 block되나요?

아닙니다. `await`는 Thread를 block하는 것이 아니라 현재 Task를 suspension합니다. 그동안 Thread는 다른 작업을 실행할 수 있고, 비동기 작업이 완료되면 Task가 재개됩니다.

---

### Q11. Task와 Task.detached의 차이는 무엇인가요?

`Task {}`는 현재 priority, actor context, task-local values를 상속합니다. `Task.detached {}`는 현재 context와 분리된 독립 작업입니다. 그래서 detached 안에서는 UI 상태나 actor-isolated 상태에 접근할 때 더 명시적으로 `await MainActor.run` 등을 사용해야 합니다.

---

### Q12. async let과 TaskGroup의 차이는 무엇인가요?

`async let`은 작업 개수가 고정되어 있을 때 적합하고, `TaskGroup`은 배열 크기처럼 런타임에 작업 개수가 결정될 때 적합합니다. TaskGroup의 결과는 작업 추가 순서가 아니라 완료 순서대로 나올 수 있으므로, 원래 순서가 필요하면 index를 같이 반환해 재정렬해야 합니다.

---

### Q13. Actor 메서드를 await로 호출하는 이유는 같은 Thread에 접근하기 위해서인가요?

아닙니다. `await actor.method()`는 동일 Thread로 이동하려는 것이 아니라, actor가 보호하는 내부 상태에 안전하게 접근할 차례를 기다리는 것입니다. 이때 Thread를 block하지 않고 현재 Task가 suspension됩니다.

---

### Q14. Actor는 동시에 호출되어도 문제가 없나요?

Actor는 내부 mutable state의 data race를 막습니다. 하지만 actor 메서드 내부에서 `await`를 만나면 그 사이 다른 호출이 들어올 수 있습니다. 따라서 토큰 갱신 중복 호출 같은 비즈니스 레벨의 race condition은 별도로 막아야 합니다.

---

### Q15. @MainActor와 MainThread의 차이는 무엇인가요?

MainThread는 실제 OS Thread이고, MainActor는 Swift Concurrency에서 UI 관련 상태 접근을 직렬화하는 Global Actor입니다. Apple 플랫폼에서 MainActor는 일반적으로 Main Thread와 연결되어 UI 업데이트에 사용됩니다. `DispatchQueue.main.async`는 런타임 예약 방식이고, `@MainActor`는 컴파일러가 actor isolation을 검사해주는 선언적 방식입니다.

---

### Q16. Sendable은 무엇인가요?

`Sendable`은 어떤 값을 다른 Task나 Actor 같은 비동기 실행 흐름으로 넘겨도 안전한 타입임을 나타내는 프로토콜입니다. 값 타입이고 내부 값들이 모두 Sendable이면 안전하게 다루기 쉽고, mutable class처럼 같은 인스턴스를 여러 Task에서 동시에 변경할 수 있는 타입은 Sendable하지 않습니다.

---

## ✏️ 퀴즈

### 문제 1

다음 중 Queue와 Thread의 관계로 가장 적절한 것은?

- A. Queue는 작업을 담는 추상화이고, Thread는 실제 실행 단위이다
- B. Queue 하나는 항상 Thread 하나와 1:1로 연결된다
- C. async를 사용하면 항상 새로운 Thread가 생성된다
- D. Serial Queue는 동기 실행만 가능하다

**정답: A**

---

### 문제 2

Main Thread에서 `DispatchQueue.main.sync`를 호출하면 어떤 문제가 발생할 수 있나요?

- A. 자동으로 background thread에서 실행된다
- B. Main Thread와 Main Queue가 서로 기다리는 deadlock이 발생한다
- C. QoS가 자동으로 낮아진다
- D. TaskGroup으로 변환된다

**정답: B**

---

### 문제 3

Thread Explosion이 발생하기 쉬운 상황은?

- A. async/await에서 await로 Task가 suspension되는 경우
- B. concurrent queue에 많은 작업을 넣고 각 작업이 semaphore.wait 등으로 Thread를 block하는 경우
- C. Serial Queue에 async 작업을 하나 넣은 경우
- D. MainActor에서 UI 텍스트를 변경하는 경우

**정답: B**

---

### 문제 4

`await`에 대한 설명으로 가장 적절한 것은?

- A. 현재 Thread를 block한다
- B. 현재 Task를 suspension하고, Thread는 다른 작업을 실행할 수 있다
- C. 항상 Main Thread로 전환한다
- D. DispatchQueue.sync와 동일하다

**정답: B**

---

### 문제 5

TaskGroup에 대한 설명으로 가장 적절한 것은?

- A. addTask 순서대로 결과가 보장된다
- B. 여러 child task를 만들고, 결과는 완료된 순서대로 받을 수 있다
- C. MainActor에서만 사용할 수 있다
- D. Thread를 직접 생성하는 API이다

**정답: B**

---

### 문제 6

actor reentrancy로 인해 발생할 수 있는 문제는?

- A. actor가 무조건 deadlock에 빠진다
- B. actor 메서드의 await 전후로 상태가 바뀌어 로직 일관성이 깨질 수 있다
- C. actor가 Sendable이 아니게 된다
- D. actor 내부의 let 프로퍼티를 읽을 수 없다

**정답: B**

---

### 문제 7

Sendable에 대한 설명으로 가장 적절한 것은?

- A. 다른 Task나 Actor로 넘겨도 안전한 타입임을 나타낸다
- B. 모든 class는 자동으로 Sendable이다
- C. struct는 내부 프로퍼티와 상관없이 항상 Sendable이다
- D. Sendable을 붙이면 모든 코드가 Main Thread에서 실행된다

**정답: A**

---
