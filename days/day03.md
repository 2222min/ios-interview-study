# Day 3 — Protocol Oriented Programming & Generics

**태그**: Protocol · Witness Table · Dispatch · Generics · Specialization · some/any

---

## 📝 핵심 정리


### 1. Method Dispatch 4가지 종류

_아이콘: `blue`_


### Dispatch가 뭔가요?

"어떤 메서드를 호출할지 결정하는 방식"입니다. `obj.method()`를 썼을 때 컴파일러나 런타임이 어떻게 실제 함수를 찾아가는지를 의미합니다.

### Swift의 4가지 Dispatch

### 1. Static Dispatch (가장 빠름)

컴파일 타임에 호출할 함수가 결정됩니다. 인라인 최적화도 가능해서 거의 함수 호출 비용이 없습니다.

```swift
struct Calculator {
    func add(_ a: Int, _ b: Int) -> Int { a + b }
}
let c = Calculator()
c.add(1, 2)  // 컴파일러가 어떤 add인지 100% 안다 → static dispatch
```

**적용 대상:** struct, enum 메서드, final class 메서드, 비-override 메서드

### 2. V-Table Dispatch (class 기본)

각 class가 가진 가상 함수 테이블(vtable)을 통해 간접 호출됩니다. 한 번의 포인터 추적이 추가됩니다.

```swift
class Animal {
    func speak() { print("...") }       // vtable[0]
}
class Cat: Animal {
    override func speak() { print("야옹") }  // vtable[0] 오버라이드
}

let a: Animal = Cat()
a.speak()
// 1. a의 metadata 포인터 따라가기
// 2. metadata.vtable[0]에서 함수 포인터 가져오기
// 3. 그 함수 호출 → Cat.speak 실행
```

**적용 대상:** override 가능한 class 메서드

### 3. Witness Table Dispatch (Protocol)

프로토콜 타입으로 사용할 때 사용됩니다. Protocol Witness Table(PWT)을 통한 간접 호출.

```swift
protocol Speakable {
    func speak()
}
struct Dog: Speakable {
    func speak() { print("멍멍") }
}

let s: Speakable = Dog()
s.speak()
// existential container의 PWT 포인터 따라가기 → Dog.speak 호출
```

**적용 대상:** 프로토콜 타입 변수의 메서드 호출

### 4. Message Dispatch (가장 느림)

Objective-C 런타임의 `objc_msgSend`를 통한 호출. 메시지 이름(selector)으로 함수를 찾습니다.

```swift
class Legacy: NSObject {
    @objc dynamic func action() { }  // dynamic이라 message dispatch
}
// 호출 시 selector 테이블 검색 → 캐시 → 함수 호출
// 가장 느리지만 method swizzling 같은 런타임 조작 가능
```

**적용 대상:** @objc dynamic 메서드, KVO 적용 프로퍼티

### 성능 비교

| Dispatch | 속도 | 유연성 |
|---|---|---|
| Static | ~1ns (인라인 시 0) | 없음 |
| V-Table | ~3-5ns | override |
| Witness Table | ~5-10ns | protocol 다형성 |
| Message | ~20-50ns | 런타임 조작 |

> 💡 **💡 면접 포인트:** "성능이 중요한 곳에서는 final class나 struct를 사용해 static dispatch를 유도합니다. 프로토콜은 유연성을 주지만 witness table dispatch 비용이 있어요. SwiftUI body가 some View를 반환하는 것도 static dispatch로 다이내믹 디스패치 비용을 피하기 위함입니다."


### 2. Protocol Witness Table (PWT) 상세

_아이콘: `green`_


### PWT가 뭔가요?

"이 타입이 프로토콜의 각 메서드를 어떻게 구현했는지"를 담은 함수 포인터 배열입니다. 컴파일러가 자동으로 생성합니다.

### 예시로 이해하기

```swift
protocol Drawable {
    func draw()
    var color: String { get }
}

struct Circle: Drawable {
    func draw() { print("원 그리기") }
    var color: String { "red" }
}

// 컴파일러가 생성하는 PWT (의사 코드):
// Circle_Drawable_PWT:
//   [0] = &Circle.draw          // 함수 포인터
//   [1] = &Circle.color.getter  // getter 포인터
```

### 호출 흐름

```swift
let d: Drawable = Circle()
d.draw()

// 내부 동작:
// 1. existential container의 PWT 포인터 가져오기
// 2. PWT[0] (draw 슬롯)에서 함수 포인터 가져오기
// 3. 그 함수 호출 (구체 타입의 draw 실행)
```

### 중요한 함정: Protocol Extension 메서드

이게 면접에서 자주 나오는 함정입니다.

```swift
protocol Greetable {
    func greet()  // 이게 protocol requirement
}

extension Greetable {
    func greet() { print("Hello") }      // 기본 구현
    func farewell() { print("Bye") }     // ⚠️ protocol에 없는 새 메서드!
}

struct Korean: Greetable {
    func greet() { print("안녕") }
    func farewell() { print("잘가") }
}

// 케이스 1: 구체 타입 변수
let k: Korean = Korean()
k.greet()      // "안녕" (static dispatch)
k.farewell()   // "잘가" (static dispatch)

// 케이스 2: 프로토콜 타입 변수
let g: Greetable = Korean()
g.greet()      // "안녕" ← greet은 PWT에 있음 → 동적 디스패치
g.farewell()   // "Bye"  ⚠️← farewell은 PWT에 없음! 
                //          static dispatch로 extension 기본 구현 호출!
```

### 왜 이런 일이 일어나나요?

핵심 규칙:

- **Protocol 본문에 선언된 메서드**: PWT에 등록 → dynamic dispatch

- **Extension에서만 정의된 메서드**: PWT에 없음 → static dispatch

즉, 프로토콜 타입으로 사용할 땐 컴파일러가 "Greetable이 가진 메서드는 뭐지?" 하고 본문만 봅니다. extension의 farewell()은 인식 못하고, 컴파일 타임에 Greetable extension의 기본 구현으로 묶어버립니다.

### 해결법

```swift
// ✅ 진짜로 override 가능하게 하려면 protocol 본문에 명시
protocol Greetable {
    func greet()
    func farewell()  // ← 본문에 선언!
}

extension Greetable {
    func greet() { print("Hello") }
    func farewell() { print("Bye") }  // 기본 구현
}

struct Korean: Greetable {
    func greet() { print("안녕") }
    func farewell() { print("잘가") }
}

let g: Greetable = Korean()
g.farewell()  // 이제 "잘가" 호출됨 (PWT에 있으므로)
```

> 💡 **💡 면접 킬러 포인트:** "protocol extension의 메서드가 protocol requirement에 선언되어 있지 않으면, 그 메서드는 witness table에 등록되지 않아 dynamic dispatch가 불가능합니다. 프로토콜 타입으로 사용할 때 예상과 다른 동작을 유발하는 가장 대표적인 함정이죠."


### 3. Generics와 Specialization

_아이콘: `purple`_


### Generics가 뭔가요?

"여러 타입에 대해 동작하는 코드를 한 번만 작성"하는 기법입니다.

```swift
// Generic이 없다면:
func swapInts(_ a: inout Int, _ b: inout Int) { ... }
func swapStrings(_ a: inout String, _ b: inout String) { ... }
func swapDoubles(_ a: inout Double, _ b: inout Double) { ... }
// 타입별로 다 만들어야 함...

// Generic으로:
func swap<T>(_ a: inout T, _ b: inout T) {
    let temp = a
    a = b
    b = temp
}
// 한 번 작성으로 모든 타입에 대응!
```

### Generic은 어떻게 컴파일되나요?

두 가지 경로가 있습니다.

### 경로 1: Specialization (최적화 ON, 빠름)

컴파일러가 호출 사이트의 구체 타입을 보고 **전용 함수**를 만들어냅니다.

```swift
// 원본:
func process<T>(_ value: T) { ... }

// 사용:
process(42)        // Int로 호출
process("hello")   // String으로 호출

// 컴파일러가 생성:
func process_Int(_ value: Int) { ... }      // Int 전용 사본
func process_String(_ value: String) { ... } // String 전용 사본
// 각각 인라인 가능, 타입 메타데이터 불필요 → 빠름!
```

### 경로 2: Unspecialized (느림)

컴파일러가 구체 타입을 모르거나 specialization을 못할 때(모듈 경계 등)는 Value Witness Table(VWT)을 통해 런타임에 처리합니다.

```swift
// VWT를 통한 런타임 동작:
// 1. T의 size, alignment를 VWT에서 조회
// 2. 적절한 메모리 할당 (스택 or 힙)
// 3. T의 copy 함수를 VWT에서 조회하여 복사
// 4. T의 destroy 함수를 VWT에서 조회하여 해제
// 매 단계마다 VWT 간접 호출 → 성능 비용
```

### @inlinable로 모듈 경계 넘기

일반적으로 다른 모듈의 generic 함수는 specialization이 안 됩니다(컴파일러가 본문을 모르니까). `@inlinable`을 붙이면 본문이 모듈 인터페이스에 포함되어 specialization이 가능해집니다.

```swift
// ModuleA의 코드:
public func processItems<T>(_ items: [T]) -> Int {
    return items.count  
}
// 다른 모듈에서 specialization 불가

// 해결:
@inlinable
public func processItems<T>(_ items: [T]) -> Int {
    return items.count
}
// 본문이 노출됨 → 호출 모듈에서 specialization 가능
```

**Trade-off:**

- 장점: 성능 향상

- 단점: 바이너리 크기 증가, ABI 안정성 제약 (구현 변경 시 클라이언트 재컴파일 필요)

### Generic Constraint

```swift
// where 절로 제약 추가
func max<T: Comparable>(_ a: T, _ b: T) -> T {
    return a > b ? a : b  // Comparable 제약 덕분에 > 사용 가능
}

// 다중 제약
func process<T: Hashable & Codable>(_ item: T) { ... }

// Associated type 제약
extension Array where Element: Numeric {
    func sum() -> Element {
        return reduce(0, +)
    }
}
```

> 💡 **💡 면접 포인트:** "Generic 코드는 specialization이 핵심입니다. 같은 모듈 내부에선 -O 최적화가 자동으로 specialization을 적용하지만, 모듈 경계를 넘으면 VWT 기반 동적 처리로 떨어집니다. 라이브러리 작성 시 핫패스 함수에는 @inlinable을 고려하되, ABI 안정성과 바이너리 크기 trade-off를 따져야 합니다."


### 4. some vs any (Swift 5.7+)

_아이콘: `orange`_


### some Protocol (Opaque Type)

"어떤 구체 타입인지는 숨기지만, **컴파일 타임에 하나로 고정**된다"는 의미입니다.

```swift
func makeShape() -> some Shape {
    return Circle(radius: 5)
}
// 호출하는 쪽에선 어떤 타입인지 모름 (Shape이라는 것만 알 수 있음)
// 하지만 컴파일러는 알고 있음 (Circle)
// → static dispatch 가능, existential 오버헤드 없음

// 제약: 항상 같은 타입을 반환해야 함
func makeShape(round: Bool) -> some Shape {
    if round {
        return Circle(radius: 5)
    } else {
        return Square(side: 3)  // ❌ 컴파일 에러! 타입이 다름
    }
}
```

### any Protocol (Existential Type)

"**실행 시점에 타입이 결정**되는 컨테이너"입니다. Existential Container를 의미합니다.

```swift
func makeShape(round: Bool) -> any Shape {
    if round {
        return Circle(radius: 5)
    } else {
        return Square(side: 3)  // ✅ OK! 다른 타입도 됨
    }
}
// 유연하지만 비용이 있음:
// - Existential Container 사용 (5 words)
// - 24B 초과 시 힙 할당
// - Witness Table dispatch (간접 호출)
```

### 성능 비교

| 항목 | some Shape | any Shape |
|---|---|---|
| 메모리 | 구체 타입 크기 | 5 words + (값 크기) |
| 함수 호출 | ~1ns (인라인 가능) | ~5-20ns (PWT) |
| 유연성 | 고정 타입 | 조건부 다른 타입 |
| Self/AssocType 사용 | 자유롭게 | 제약 있음 |

### 언제 어느 걸 써야 하나요?

| 상황 | 선택 |
|---|---|
| SwiftUI body, View modifier | **some** |
| 한 번 호출에 한 종류만 반환 | **some** |
| 조건부로 다른 타입 반환 | **any** |
| Array<Shape> 같은 이종 컬렉션 | **any** (Array<any Shape>) |
| 모듈 인터페이스, 유연성 우선 | **any** |
| 성능 중요한 hot path | **some** 또는 generic |

### Primary Associated Type (Swift 5.7+)

이전엔 `any Collection`처럼 type erasure가 필요했지만, 이제 꺾쇠로 명시 가능합니다.

```swift
// 이전 (Swift 5.6 이전)
let nums: AnyCollection<Int> = [1, 2, 3]

// 현재 (Swift 5.7+)
let nums: any Collection<Int> = [1, 2, 3]
// Collection의 primary associated type이 Element이기 때문
```

> 💡 **💡 면접 답변 예시:** "저는 모듈 간 인터페이스에서는 any Protocol을 사용하고, 모듈 내부 구현에서는 some Protocol이나 구체 generic을 사용합니다. 특히 SwiftUI의 body가 some View를 반환하는 이유는, 컴파일러가 View 트리의 구체 타입을 알아야 효율적인 diff 알고리즘을 수행할 수 있기 때문입니다. 이종 데이터를 담는 컬렉션엔 any Protocol<...>를 활용합니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. protocol extension 메서드가 override되지 않는 경우는? `[심화 / 빈출]`

protocol requirement에 선언되지 않은 extension 전용 메서드입니다.

이런 메서드는 PWT(Protocol Witness Table)에 등록되지 않아 dynamic dispatch가 불가능합니다. 프로토콜 타입으로 사용할 때는 항상 extension의 기본 구현이 호출됩니다.

해결: protocol 본문에 메서드를 명시적으로 선언하면 PWT에 등록되어 정상적으로 동작합니다.


### Q2. some과 any의 차이를 한 줄로 설명한다면? `[기본 / 빈출]`

**some = 컴파일 타임에 하나의 구체 타입으로 고정** (static dispatch, 빠름).
**any = 런타임에 어떤 타입이든 담을 수 있는 컨테이너** (dynamic dispatch, 유연하지만 약간 느림).

SwiftUI body는 some View를 반환합니다 — 한 View struct가 한 가지 모양만 그리니까요. 반대로 [any Drawable] 배열은 Circle, Square를 섞어 담을 수 있습니다.


### Q3. @inlinable의 trade-off는? `[심화]`

**장점:** 모듈 경계를 넘어서도 specialization 가능 → 성능 향상.

**단점:**
1. 함수 본문이 모듈 인터페이스에 노출됨
2. 바이너리 크기 증가
3. ABI 안정성 제약 (구현 변경 시 클라이언트 재컴파일 필요)
4. 정보 은닉 약화 (라이브러리 사용자가 내부 구현을 볼 수 있음)

가이드: 라이브러리에서 정말 hot path인 작은 함수에만 선택적으로 적용. ABI를 잠그기 전에 신중히 검토.


### Q4. Witness Table과 V-Table의 차이는? `[심화]`

둘 다 함수 포인터 배열이지만 사용 목적과 구조가 다릅니다.

**V-Table (Virtual Table):** class 인스턴스의 metadata에 포함됨. 상속 계층의 가상 메서드들을 담음. override 시 vtable 슬롯이 새 함수로 교체됨.

**Witness Table (Protocol Witness Table):** 타입과 프로토콜의 조합마다 별도 생성. struct, enum, class 모두 적용. 한 타입이 여러 프로토콜을 채택하면 여러 PWT를 가짐.

예: Dog가 Animal과 Comparable을 채택하면 Dog의 Animal_PWT, Dog의 Comparable_PWT가 각각 존재.


### Q5. final class와 struct 중 어느 게 더 빠른가요? `[기본]`

**둘 다 static dispatch라서 호출 비용은 동일합니다.** 차이는 다른 곳에서 옵니다:

**final class:** 항상 힙 할당, retain/release 비용. 큰 데이터를 참조로 공유하면 효율적.

**struct:** 인라인 저장(보통 스택), 복사 시 데이터 전체 복사. 작은 데이터면 매우 빠름. 큰 데이터면 복사 비용 발생 (단, COW로 완화 가능).

일반론: 작은 값/불변 데이터는 struct, 큰 데이터/공유 필요한 건 class. 단, 표준 컬렉션(Array, Dictionary)은 struct지만 COW로 비용을 최소화합니다.


---


## ✏️ 퀴즈


### 문제 1

protocol extension에 정의된 메서드가 Witness Table에 등록되려면?


   **A.** extension에 정의하기만 하면 자동 등록된다

✅ **B.** protocol 본문에 requirement로 선언해야 한다

   **C.** @objc 또는 dynamic 키워드를 붙여야 한다

   **D.** final 키워드를 붙여야 한다


**정답**: B


💡 **힌트**: PWT(Protocol Witness Table)에는 protocol requirement만 등록됩니다.


### 문제 2

다음 중 가장 빠른 dispatch는?


✅ **A.** Static Dispatch (struct, final class)

   **B.** V-Table Dispatch (class)

   **C.** Witness Table Dispatch (protocol)

   **D.** Message Dispatch (@objc dynamic)


**정답**: A


💡 **힌트**: 컴파일 타임에 결정되어 인라인 가능한 것이 가장 빠릅니다.


### 문제 3

some Shape와 any Shape의 가장 큰 차이는?


   **A.** some은 protocol이고 any는 class다

✅ **B.** some은 컴파일 타임 고정, any는 런타임 결정

   **C.** some은 빠르고 any는 항상 같은 속도다

   **D.** 둘은 완전히 동일하다


**정답**: B


💡 **힌트**: some은 opaque type, any는 existential type입니다.


