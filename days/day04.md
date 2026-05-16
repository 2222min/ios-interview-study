# Day 4 — Concurrency: GCD와 Swift Concurrency

**태그**: GCD · DispatchQueue · async/await · Actor · Sendable · Thread Pool

---

## 📝 핵심 정리


### 1. GCD (Grand Central Dispatch) 기초

_아이콘: `blue`_


### GCD가 뭔가요?

Apple이 만든 저수준 동시성 API입니다. 스레드를 직접 관리하는 대신 "큐(Queue)"에 작업을 넣으면 시스템이 알아서 적절한 스레드에 분배해 실행합니다.

### 왜 만들었나요?

예전에는 `pthread`나 `NSThread`로 직접 스레드를 만들었습니다. 하지만 스레드를 너무 많이 만들면 메모리/CPU가 낭비되고, 적게 만들면 활용도가 떨어집니다. GCD는 시스템이 보유한 **스레드 풀**을 효율적으로 공유합니다.

### 핵심 개념: Queue

```swift
// Serial Queue: 하나씩 순서대로 실행
let serial = DispatchQueue(label: "com.app.serial")
serial.async { print("A") }
serial.async { print("B") }
serial.async { print("C") }
// 출력: A, B, C (항상 이 순서)

// Concurrent Queue: 여러 개 동시 실행 가능
let concurrent = DispatchQueue(label: "com.app.concurrent", attributes: .concurrent)
concurrent.async { print("A") }
concurrent.async { print("B") }
concurrent.async { print("C") }
// 출력: 순서 보장 안 됨 (병렬 실행)
```

### 중요한 큐들

| 큐 | 설명 |
|---|---|
| `DispatchQueue.main` | 메인 스레드. UI 업데이트는 항상 여기서 |
| `DispatchQueue.global()` | 기본 글로벌 큐 (concurrent) |
| `DispatchQueue(label:)` | 커스텀 큐 (기본 serial) |

### sync vs async

```swift
// async: 작업을 큐에 넣고 즉시 리턴 (non-blocking)
queue.async {
    longTask()  // 백그라운드에서 실행
}
print("바로 출력됨")

// sync: 작업이 끝날 때까지 기다림 (blocking)
queue.sync {
    longTask()  // 끝날 때까지 대기
}
print("longTask 완료 후 출력")
```

### 가장 흔한 패턴

```swift
// 백그라운드에서 무거운 작업 → UI는 메인에서 업데이트
DispatchQueue.global().async {
    let result = heavyComputation()
    
    DispatchQueue.main.async {
        self.label.text = result  // UI 업데이트
    }
}
```

### ⚠️ 절대 하지 말 것: main.sync

```swift
// ❌ 데드락! 영원히 멈춤
DispatchQueue.main.async {
    DispatchQueue.main.sync {  // 메인 스레드에서 메인 스레드를 기다림
        // 도달 불가능
    }
}
// 메인이 main.sync를 기다리는 중이라 그 큐를 처리 못함 → 영원히 대기
```

> 💡 **💡 면접 포인트:** "GCD는 스레드 풀 위에 큐 추상화를 올린 시스템입니다. async/await가 등장한 후에도 여전히 강력한 도구이지만, 새 코드에서는 Swift Concurrency가 더 안전하고 직관적입니다. GCD의 큰 함정은 thread explosion과 priority inversion인데, Swift Concurrency는 cooperative thread pool로 이걸 원천 차단합니다."


### 2. QoS와 Thread Explosion

_아이콘: `green`_


### QoS (Quality of Service)

작업의 우선순위를 시스템에 알려주는 힌트입니다. 시스템은 이를 보고 CPU/스레드 할당을 조정합니다.

| QoS | 용도 |
|---|---|
| `.userInteractive` | UI 업데이트, 애니메이션 (가장 높음) |
| `.userInitiated` | 사용자 액션 결과 (탭 후 로딩) |
| `.default` | 기본값 |
| `.utility` | 프로그레스 바 있는 긴 작업 |
| `.background` | 백업, 인덱싱 (사용자 모름) |

```swift
DispatchQueue.global(qos: .userInitiated).async {
    let data = fetchData()  // 사용자 대기 중이라 빠르게
    DispatchQueue.main.async {
        self.show(data)
    }
}
```

### Priority Inversion (우선순위 역전)

높은 우선순위 작업이 낮은 우선순위 작업을 기다리게 되는 현상입니다.

```swift
// 시나리오:
// Low qos가 lock 보유 중
// High qos가 같은 lock 요청 → Low가 끝날 때까지 대기
// → High의 우선순위가 무력화됨

// GCD는 이를 자동으로 감지하여 Low의 우선순위를 일시적으로 올립니다
// (Priority Inheritance)
// 단, 수동 NSLock에서는 GCD가 모르는 경우도 있음
```

### Thread Explosion (스레드 폭발)

GCD의 가장 큰 함정입니다. 블로킹 코드가 있을 때 발생합니다.

```swift
// ❌ Thread Explosion 유발
let semaphore = DispatchSemaphore(value: 0)
for i in 0..<1000 {
    DispatchQueue.global().async {
        semaphore.wait()  // 블로킹!
        // GCD: "이 스레드가 막혔네? 새 스레드 만들자"
        // → 다음 작업도 블로킹 → 또 새 스레드
        // → 64개 스레드 한도 도달 → 시스템 불안정
        doWork()
        semaphore.signal()
    }
}
```

### 해결법

```swift
// 방법 1: concurrentPerform — 시스템이 코어 수에 맞게 분배
DispatchQueue.concurrentPerform(iterations: 1000) { i in
    doWork(i)  // 자동으로 적절한 병렬도
}

// 방법 2: OperationQueue 동시 실행 제한
let queue = OperationQueue()
queue.maxConcurrentOperationCount = 4

// 방법 3 (권장): Swift Concurrency
// thread pool이 코어 수로 고정되어 있어 thread explosion 원천 차단
```

> 💡 **💡 면접 포인트:** "GCD에서 semaphore.wait, NSLock, sync, DispatchGroup.wait 같은 블로킹 호출을 async 큐에서 사용하면 thread explosion이 발생할 수 있습니다. 시스템은 막힌 스레드를 보고 처리량을 유지하려 새 스레드를 만들어내거든요. 이것이 Swift Concurrency가 도입된 큰 이유 중 하나입니다."


### 3. Swift Concurrency: async/await

_아이콘: `purple`_


### 왜 만들었나요?

GCD의 한계를 극복하기 위해서입니다.

- Callback hell 해결

- Thread explosion 방지

- 구조화된 동시성 (자식 작업 자동 관리)

- 컴파일 타임 안전성 (data race 검출)

### async/await 기본

```swift
// 이전: completion handler 지옥
func loadProfile(id: String, completion: @escaping (User?) -> Void) {
    fetchUser(id: id) { user in
        guard let user = user else {
            completion(nil)
            return
        }
        fetchPosts(userId: user.id) { posts in
            user.posts = posts
            fetchAvatar(url: user.avatarURL) { avatar in
                user.avatar = avatar
                completion(user)
            }
        }
    }
}

// async/await로:
func loadProfile(id: String) async throws -> User {
    var user = try await fetchUser(id: id)
    user.posts = try await fetchPosts(userId: user.id)
    user.avatar = try await fetchAvatar(url: user.avatarURL)
    return user
}
```

### Cooperative Thread Pool

GCD와 결정적인 차이점입니다.

- **스레드 수 = CPU 코어 수 (고정!)**

- Task가 await에서 자발적으로 스레드 양보

- 스레드를 점유하지 않고 continuation만 저장

- thread explosion 원천 차단

```swift
func fetchData() async throws -> Data {
    let url = URL(string: "https://api.com")!
    let (data, _) = try await URLSession.shared.data(from: url)
    // ↑ 여기서 스레드 반환!
    //   네트워크 완료되면 어느 스레드든 잡아서 재개
    return data
}
```

### Structured Concurrency: async let

여러 작업을 동시에 시작하고 모두 완료될 때까지 기다립니다.

```swift
func loadDashboard() async throws -> Dashboard {
    // 세 개를 동시 시작!
    async let profile = fetchProfile()
    async let posts = fetchPosts()
    async let notifications = fetchNotifications()
    
    // 모두 완료될 때까지 대기
    return try await Dashboard(
        profile: profile,
        posts: posts,
        notifications: notifications
    )
    // 자동 cancellation: 하나라도 throw하면 나머지 자동 취소
}
```

### TaskGroup: 동적 작업 모음

```swift
func fetchManyImages(urls: [URL]) async throws -> [UIImage] {
    try await withThrowingTaskGroup(of: UIImage.self) { group in
        for url in urls {
            group.addTask {
                try await fetchImage(from: url)
            }
        }
        
        var images: [UIImage] = []
        for try await image in group {
            images.append(image)
        }
        return images
    }
}
```

### Task와 Task.detached

```swift
// Task: 부모의 priority, actor context, task-local 상속
@MainActor
func userTapped() {
    Task {
        // 자동으로 @MainActor에서 시작!
        await loadData()
    }
}

// Task.detached: 아무것도 상속 안 함
@MainActor
func userTapped() {
    Task.detached {
        // 백그라운드에서 시작!
        await loadData()
    }
}
```

> 💡 **💡 면접 포인트:** "GCD는 작업을 큐에 넣고 시스템이 스레드 풀에 분배하는 모델이지만, 블로킹 코드가 있으면 thread explosion이 발생합니다. Swift Concurrency는 cooperative thread pool로 스레드 수를 코어 수로 고정하고, await에서 작업이 자발적으로 양보합니다. 또한 structured concurrency로 자식 작업의 lifetime이 부모에 묶여 누수가 없습니다."


### 4. Actor와 Sendable

_아이콘: `orange`_


### Actor가 뭔가요?

"내부 상태를 동시 접근으로부터 보호하는 참조 타입"입니다. 데이터 경합(data race)을 컴파일 타임에 막아줍니다.

```swift
// ❌ class에 mutable 상태 → race condition 위험
class BankAccount {
    var balance: Double = 0
    
    func deposit(_ amount: Double) {
        balance += amount  // 여러 스레드에서 동시 호출 시 데이터 손실 가능
    }
}

// ✅ actor로 해결
actor BankAccount {
    var balance: Double = 0
    
    func deposit(_ amount: Double) {
        balance += amount  // actor 내부에서는 동기적 접근 보장!
    }
}
```

### Actor 동작 원리

각 actor 인스턴스는 **serial executor**를 가집니다. 외부에서 actor의 메서드를 호출하면 메시지처럼 큐에 쌓이고, 한 번에 하나씩 실행됩니다.

```swift
let account = BankAccount()

// 외부에서 actor 메서드 호출 시 await 필요
Task {
    await account.deposit(100)  // 큐에 메시지 enqueue → 처리
    let bal = await account.balance
    print(bal)
}

// 동작:
// 1. account의 mailbox에 deposit 요청 추가
// 2. account가 idle이면 즉시 실행, busy면 대기
// 3. 다음 요청은 이전 것 끝나야 시작 → 순서 보장
```

### Global Actor: @MainActor

"이 코드는 메인 스레드에서만 실행돼야 한다"고 명시합니다.

```swift
@MainActor
class ViewModel: ObservableObject {
    @Published var items: [Item] = []  // UI 바인딩 → 메인 스레드 보장
    
    func load() async {
        // 백그라운드에서 실행되어도:
        let data = await fetchFromNetwork()
        items = data  // ← 자동으로 메인 스레드에서 실행됨!
    }
}

// 메서드 단위로도 가능:
class SomeClass {
    @MainActor
    func updateUI() {
        // 메인 스레드에서만 호출 가능
    }
}
```

### Sendable: 동시성 경계 통과

"이 타입은 스레드/actor 사이를 안전하게 건너갈 수 있다"는 표시입니다.

| 자동 Sendable | 아닌 것 |
|---|---|
| struct (모든 프로퍼티가 Sendable) | class (mutable state) |
| enum (모든 case가 Sendable) | function with mutable capture |
| actor (자체적으로 격리됨) | 참조 공유되는 모든 가변 상태 |

```swift
// ❌ 컴파일 에러 (Swift 6 strict concurrency)
class UnsafeCache {
    var data: [String: Any] = [:]  // mutable + not isolated
}

func processInBackground(cache: UnsafeCache) async { ... }  // ❌

// ✅ 해결 1: actor로 변환
actor SafeCache {
    var data: [String: Any] = [:]
}

// ✅ 해결 2: @unchecked Sendable (개발자가 thread safety 보장)
final class ManuallyThreadSafeCache: @unchecked Sendable {
    private let lock = NSLock()
    private var data: [String: Any] = [:]
    
    func get(_ key: String) -> Any? {
        lock.lock()
        defer { lock.unlock() }
        return data[key]
    }
}
```

### Actor Reentrancy (중요한 함정!)

actor 메서드 안에서 await을 만나면 actor lock이 일시 해제됩니다. 그 사이에 다른 호출이 들어와 상태를 바꿀 수 있습니다.

```swift
actor Counter {
    var count = 0
    
    func incrementTwice() async {
        count += 1
        await someAsyncWork()
        // ⚠️ 이 시점에서 count는 반드시 1이 아닐 수 있다!
        // await 동안 다른 호출이 count를 변경했을 수도 있음
        count += 1
    }
}

// 해결: await 전후로 상태를 다시 검증하거나,
// await 없이 동기적으로 처리할 수 있도록 분리
```

> 💡 **💡 면접 포인트:** "Actor는 serial executor 기반의 격리로 데이터 경합을 컴파일 타임에 막습니다. 하지만 reentrancy 함정이 있어 await 전후로 상태가 변할 수 있다는 점을 인지해야 합니다. Sendable은 동시성 경계를 안전하게 통과할 수 있는지 표시하고, Swift 6의 strict concurrency mode에서는 모든 cross-actor 데이터가 Sendable이어야 합니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. GCD에서 thread explosion은 왜 일어나나요? `[심화 / 빈출]`

async 큐의 작업이 블로킹(semaphore.wait, NSLock 등)되면, GCD는 \"처리량 유지\"를 위해 새 스레드를 만들어 다음 작업을 처리하려 합니다. 그런데 그 작업도 블로킹되면 또 새 스레드... 이렇게 64개 스레드 한도까지 도달할 수 있습니다.

해결: `concurrentPerform`으로 코어 수에 맞게 분배, OperationQueue의 maxConcurrentOperationCount 제한, 또는 Swift Concurrency 사용 (cooperative thread pool은 항상 코어 수만큼만 사용).


### Q2. Task와 Task.detached의 차이는? `[기본 / 빈출]`

**Task**: 부모 컨텍스트의 priority, actor isolation, task-local values를 상속합니다. `@MainActor` 함수 안에서 `Task { }`를 만들면 자동으로 MainActor에서 실행됩니다.

**Task.detached**: 아무것도 상속하지 않습니다. 완전히 독립적인 새 작업을 만들죠. `@MainActor` 함수 안에서 백그라운드 작업이 필요하면 사용합니다.

일반적으로 Task가 권장됩니다. detached는 명확한 이유가 있을 때만.


### Q3. actor reentrancy 문제를 설명해주세요 `[심화 / 빈출]`

actor의 메서드가 await을 만나면 일시적으로 lock이 해제됩니다. 그 사이에 다른 호출이 actor의 상태를 변경할 수 있습니다.

예를 들어 캐시에 값을 넣기 전 네트워크 호출 await을 하는 동안, 다른 호출이 같은 키에 다른 값을 넣을 수 있습니다.

**해결 방법:**
1. await 전에 필요한 상태를 로컬 변수에 캡처
2. await 후 상태를 다시 검증
3. critical section을 await 없는 동기 메서드로 분리
4. invalidation 패턴으로 stale 결과 무시


### Q4. @MainActor와 DispatchQueue.main의 차이는? `[기본 / 빈출]`

**DispatchQueue.main**: GCD 기반. async로 메인 큐에 작업 enqueue. 컴파일 타임 안전성 없음 — 메인이어야 하는 코드를 백그라운드에서 호출해도 컴파일은 됨.

**@MainActor**: Swift Concurrency 기반. 컴파일러가 메인 스레드 격리를 강제. 백그라운드에서 @MainActor 메서드 호출 시 await 필수, 안 쓰면 컴파일 에러.

새 코드에서는 @MainActor를 권장합니다. 컴파일 타임에 실수를 잡아주니까요.


### Q5. async let과 TaskGroup의 차이는? `[심화]`

**async let**: 정적인 작업 묶음. 컴파일 타임에 작업 개수가 정해져 있을 때.

**TaskGroup**: 동적인 작업 묶음. 런타임에 작업 개수가 결정될 때 (예: 배열의 모든 원소에 대해 fetch).

예시:

```swift
// 작업 3개 고정 → async let\nasync let a = fetchA()\nasync let b = fetchB()\nasync let c = fetchC()\n\n// 배열 크기에 따라 동적 → TaskGroup\nawait withTaskGroup(of: ...) { group in\n  for url in urls {\n    group.addTask { await fetch(url) }\n  }\n}
```


---


## ✏️ 퀴즈


### 문제 1

다음 중 MainActor에 대한 설명으로 가장 적절한 것은?


✅ **A.** 메인 스레드에서만 실행되어야 하는 코드를 보장하기 위한 Global Actor이다

   **B.** 백그라운드 스레드에서 높은 우선순위로 실행을 보장하는 Actor이다

   **C.** 여러 Actor 간의 메시지 전달을 최적화하기 위한 도구이다

   **D.** 비동기 작업을 병렬로 실행하기 위해 자동 생성되는 Actor이다


**정답**: A


💡 **힌트**: @MainActor는 UI 업데이트와 스레드 안정성에 관련이 있습니다.


### 문제 2

Swift Concurrency의 cooperative thread pool의 가장 큰 장점은?


   **A.** 스레드 수가 무제한으로 증가할 수 있다

✅ **B.** 스레드 수가 CPU 코어 수로 고정되어 thread explosion이 없다

   **C.** GCD보다 항상 빠르다

   **D.** 메인 스레드에서만 동작한다


**정답**: B


💡 **힌트**: GCD의 가장 큰 함정이었던 thread explosion을 원천 차단하는 게 핵심입니다.


### 문제 3

actor reentrancy로 인해 발생할 수 있는 문제는?


   **A.** actor가 deadlock에 빠진다

✅ **B.** await 전후로 상태가 변경되어 일관성이 깨질 수 있다

   **C.** actor가 자동으로 메모리에서 해제된다

   **D.** 컴파일 에러가 발생한다


**정답**: B


💡 **힌트**: await 동안 다른 호출이 actor의 상태를 변경할 수 있다는 점이 핵심입니다.


