# Day 3 — Protocol Oriented Programming & Generics

**태그**: Protocol · Protocol Extension · Witness Table · Dispatch · Generics · Specialization · some/any · associatedtype · Type Erasure

---

## 🧭 오늘의 핵심 한 줄

Swift에서 Protocol Oriented Programming과 Generic을 이해하려면 결국 아래 질문에 답할 수 있어야 합니다.

> **이 타입 정보를 컴파일 타임에 유지할 것인가, 런타임에 지울 것인가?**

- 타입 정보가 필요 없고 구현체가 하나라면 **Concrete Type**
- 타입 관계와 성능이 중요하면 **Generic / some**
- 런타임 다형성이나 서로 다른 타입을 한 컬렉션에 담아야 하면 **any**
- `associatedtype` / `Self requirement`가 있으면 **Generic 또는 Type Erasure**를 우선 고려

---

## 📝 핵심 정리

## 1. Protocol Oriented Programming이란?

Protocol Oriented Programming, 즉 POP는 클래스 상속보다 **protocol을 중심으로 역할과 기능을 정의하는 설계 방식**입니다.

Swift에서는 `class`뿐 아니라 `struct`, `enum`도 protocol을 채택할 수 있습니다. 그래서 값 타입 기반 설계에서도 다형성을 사용할 수 있습니다.

```swift
protocol UserRepresentable {
    var name: String { get }
}

struct User: UserRepresentable {
    let name: String
}

enum Guest: UserRepresentable {
    case anonymous

    var name: String { "guest" }
}
```

### OOP와 비교했을 때 POP의 장점

OOP는 보통 class 상속을 중심으로 공통 기능을 재사용합니다. 하지만 class 상속은 아래 문제가 생길 수 있습니다.

- 단일 상속만 가능
- 상위 class에 강하게 결합됨
- reference type 공유로 인해 사이드 이펙트가 생길 수 있음
- 상속 계층이 깊어질수록 추적이 어려움

반면 POP는 역할을 protocol 단위로 나누고 조합할 수 있습니다.

```swift
protocol Configurable {
    func configure()
}

protocol Trackable {
    func track()
}

final class ProductCell: UIView, Configurable, Trackable {
    func configure() {}
    func track() {}
}
```

면접에서는 이렇게 답하면 좋습니다.

> Protocol Oriented Programming은 클래스 상속보다 프로토콜을 중심으로 타입의 역할과 요구사항을 정의하는 설계 방식입니다. Swift에서는 struct, enum, class 모두 protocol을 채택할 수 있기 때문에 value type 기반 설계에서도 다형성을 사용할 수 있습니다. 또한 protocol extension을 통해 기본 구현을 제공할 수 있어, 상속 없이도 코드 재사용과 기능 조합이 가능합니다.

---

## 2. Protocol과 Protocol Extension

### protocol은 요구사항을 정의한다

```swift
protocol Flyable {
    func fly()
}
```

이 코드는 `Flyable`을 채택한 타입은 반드시 `fly()`를 구현해야 한다는 계약입니다.

### protocol extension은 기본 구현과 공통 기능을 제공한다

```swift
extension Flyable {
    func fly() {
        print("날아갑니다")
    }
}
```

이렇게 하면 `Flyable`을 채택한 타입이 직접 `fly()`를 구현하지 않아도 기본 구현을 사용할 수 있습니다.

```swift
struct Bird: Flyable { }

Bird().fly() // 날아갑니다
```

### 주의: protocol과 extension에는 저장 프로퍼티를 둘 수 없다

```swift
protocol UserRepresentable {
    var name: String { get }
}
```

위처럼 요구사항은 가능하지만 아래처럼 저장 프로퍼티 기본값은 불가능합니다.

```swift
protocol UserRepresentable {
    // var name: String = "min" // ❌ 불가능
}
```

`protocol extension`에서도 저장 프로퍼티는 불가능하고, computed property 기본 구현만 가능합니다.

```swift
extension UserRepresentable {
    var displayName: String {
        name
    }
}
```

> 면접 포인트: `protocol`은 요구사항, `protocol extension`은 기본 구현과 공통 기능 제공입니다.

---

## 3. Method Dispatch 4가지 종류

### Dispatch가 뭔가요?

Dispatch는 `obj.method()`를 호출했을 때 **어떤 실제 함수를 실행할지 결정하는 방식**입니다.

### 1) Static Dispatch

컴파일 타임에 호출할 함수가 결정됩니다. 가장 빠르고 인라인 최적화가 가능합니다.

```swift
struct Calculator {
    func add(_ a: Int, _ b: Int) -> Int {
        a + b
    }
}

let c = Calculator()
c.add(1, 2) // 컴파일러가 호출 대상을 정확히 앎
```

주로 `struct`, `enum`, `final class`, private 메서드 등에서 발생합니다.

### 2) V-Table Dispatch

class의 override 가능한 메서드는 vtable을 통해 호출됩니다.

```swift
class Animal {
    func speak() { print("...") }
}

class Cat: Animal {
    override func speak() { print("야옹") }
}

let animal: Animal = Cat()
animal.speak() // vtable을 통해 Cat.speak 호출
```

### 3) Witness Table Dispatch

protocol requirement를 protocol 타입으로 호출할 때 사용됩니다.

```swift
protocol Speakable {
    func speak()
}

struct Dog: Speakable {
    func speak() { print("멍") }
}

let value: any Speakable = Dog()
value.speak()
```

`any Speakable`은 existential container이고, 내부에 실제 값과 witness table 포인터를 가집니다.

### 4) Message Dispatch

Objective-C 런타임의 `objc_msgSend`를 통한 호출입니다.

```swift
class Legacy: NSObject {
    @objc dynamic func action() {}
}
```

`@objc dynamic`, KVO, selector 기반 호출에서 사용됩니다.

### 성능 비교

| Dispatch | 결정 시점 | 대표 사례 | 특징 |
|---|---|---|---|
| Static Dispatch | 컴파일 타임 | struct, enum, final class | 가장 빠름, 인라인 가능 |
| V-Table Dispatch | 런타임 | class override | 상속 기반 다형성 |
| Witness Table Dispatch | 런타임 | any Protocol | protocol 기반 다형성 |
| Message Dispatch | 런타임 | @objc dynamic | Objective-C 런타임 유연성 |

> 숫자로 외우기보다 "Static은 컴파일 타임, 나머지는 간접 호출 비용이 있다" 정도로 이해하면 충분합니다.

---

## 4. Protocol Witness Table과 Protocol Extension 함정

### PWT가 뭔가요?

Protocol Witness Table은 **어떤 타입이 프로토콜의 요구사항을 어떻게 구현했는지 담은 함수 포인터 테이블**입니다.

```swift
protocol Drawable {
    func draw()
    var color: String { get }
}

struct Circle: Drawable {
    func draw() { print("원 그리기") }
    var color: String { "red" }
}
```

컴파일러는 개념적으로 이런 테이블을 만듭니다.

```swift
// Circle_Drawable_PWT
// [0] = Circle.draw
// [1] = Circle.color.getter
```

`any Drawable`로 호출하면 existential container 안의 witness table을 따라가서 실제 구현을 호출합니다.

```swift
let drawable: any Drawable = Circle()
drawable.draw()
```

### protocol extension 메서드 함정

```swift
protocol Greetable {
    func greet()
}

extension Greetable {
    func greet() { print("Hello") }
    func farewell() { print("Bye") }
}

struct Korean: Greetable {
    func greet() { print("안녕") }
    func farewell() { print("잘가") }
}
```

구체 타입으로 호출하면 `Korean.farewell()`이 호출됩니다.

```swift
let korean = Korean()
korean.farewell() // 잘가
```

하지만 protocol 타입으로 보면 다릅니다.

```swift
let value: any Greetable = Korean()
value.greet()    // 안녕
value.farewell() // Bye
```

왜냐하면 `farewell()`은 protocol requirement가 아니기 때문에 PWT에 등록되지 않습니다. 따라서 `any Greetable` 입장에서는 `Korean.farewell()`을 다형적으로 호출할 방법이 없습니다.

### 해결법

진짜 override처럼 동작해야 한다면 protocol 본문에 requirement로 선언해야 합니다.

```swift
protocol Greetable {
    func greet()
    func farewell()
}

extension Greetable {
    func greet() { print("Hello") }
    func farewell() { print("Bye") }
}

struct Korean: Greetable {
    func greet() { print("안녕") }
    func farewell() { print("잘가") }
}

let value: any Greetable = Korean()
value.farewell() // 잘가
```

> 면접 킬러 포인트: protocol extension의 메서드가 protocol requirement에 선언되어 있지 않으면 witness table에 들어가지 않습니다. 그래서 protocol 타입으로 호출할 때 extension 기본 구현이 static하게 선택될 수 있습니다.

---

## 5. some Protocol vs any Protocol

## some Protocol = Opaque Type

`some Protocol`은 **프로토콜을 만족하는 하나의 구체 타입을 숨긴다**는 의미입니다.

```swift
protocol Animal {
    func speak()
}

struct Dog: Animal {
    func speak() { print("멍") }
}

func makeAnimal() -> some Animal {
    Dog()
}
```

호출자는 실제 타입이 `Dog`인지 모르지만, 컴파일러는 알고 있습니다. 그래서 최적화에 유리하고 existential container가 필요 없습니다.

### some은 여러 타입 중 아무거나가 아니다

```swift
struct Cat: Animal {
    func speak() { print("야옹") }
}

func makeAnimal(_ isDog: Bool) -> some Animal {
    if isDog {
        return Dog()
    } else {
        return Cat() // ❌ 불가능
    }
}
```

`some Animal`은 `Animal`을 만족하는 아무 타입이나 반환한다는 뜻이 아닙니다. **하나의 concrete type으로 고정되어야 합니다.**

서로 다른 타입을 반환해야 한다면 `any Animal`을 사용하거나 enum으로 감싸야 합니다.

```swift
func makeAnimal(_ isDog: Bool) -> any Animal {
    if isDog {
        return Dog()
    } else {
        return Cat()
    }
}
```

## any Protocol = Existential Type

`any Protocol`은 protocol을 만족하는 값을 담을 수 있는 existential container입니다.

```swift
let animals: [any Animal] = [Dog(), Cat()]
```

서로 다른 concrete type을 하나의 배열에 담을 수 있습니다. 대신 concrete type 정보가 지워지고 witness table dispatch가 발생할 수 있습니다.

### some vs any 비교

| 구분 | some Protocol | any Protocol |
|---|---|---|
| 개념 | Opaque Type | Existential Type |
| 실제 타입 | 하나로 고정 | 런타임에 다양할 수 있음 |
| 타입 결정 | 컴파일러가 알고 있음 | 박스 내부에 숨겨짐 |
| existential container | 없음 | 있음 |
| 성능 | 최적화 유리 | 간접 호출 비용 가능 |
| 사용 예 | SwiftUI `some View` | `[any Animal]`, 런타임 다형성 |

면접 답변 예시:

> `some Protocol`은 실제 concrete type을 외부에 숨기지만 컴파일러는 알고 있는 opaque type입니다. 하나의 구체 타입으로 고정되어야 하고 성능 최적화에 유리합니다. 반면 `any Protocol`은 existential type으로, 여러 concrete type을 런타임에 담을 수 있지만 existential container와 witness table dispatch 비용이 생길 수 있습니다.

---

## 6. Generic과 some Protocol의 관계

함수 파라미터 위치에서 `some Protocol`은 대부분 generic의 축약 문법처럼 볼 수 있습니다.

```swift
func printName<T: UserRepresentable>(_ user: T) {
    print(user.name)
}
```

```swift
func printName(_ user: some UserRepresentable) {
    print(user.name)
}
```

두 함수는 단일 파라미터 기준으로 거의 동일하게 이해할 수 있습니다.

- 호출 시점에 concrete type이 정해짐
- existential container를 만들지 않음
- `any UserRepresentable`보다 최적화에 유리함

하지만 generic은 타입 파라미터 `T`를 여러 위치에서 재사용할 수 있습니다.

```swift
func compare<T: UserRepresentable>(_ lhs: T, _ rhs: T) {
    print(lhs.name == rhs.name)
}
```

이 함수는 `lhs`와 `rhs`가 반드시 같은 concrete type이어야 합니다.

반면 아래 코드는 각각의 `some`이 독립적인 opaque parameter입니다.

```swift
func compare(_ lhs: some UserRepresentable, _ rhs: some UserRepresentable) {
    print(lhs.name == rhs.name)
}
```

`lhs`와 `rhs`는 서로 다른 concrete type이어도 됩니다.

즉 아래 generic과 유사합니다.

```swift
func compare<T: UserRepresentable, U: UserRepresentable>(_ lhs: T, _ rhs: U) {
    print(lhs.name == rhs.name)
}
```

> 단순 입력이면 `some`이 간결하고, 여러 파라미터나 반환 타입 사이의 관계를 표현해야 하면 generic이 더 적합합니다.

---

## 7. Generic 반환 타입과 some 반환 타입의 차이

아래 코드는 문제가 있습니다.

```swift
func makeUser<T: UserRepresentable>() -> T {
    return User(name: "min") // ❌ 불가능
}
```

왜냐하면 generic의 `T`는 보통 **호출자가 결정하는 타입**이기 때문입니다.

```swift
struct User: UserRepresentable {
    let name: String
}

struct Admin: UserRepresentable {
    let name: String
}

let admin: Admin = makeUser()
```

`makeUser<T>() -> T`라고 선언하면 호출자는 `T == Admin`을 기대할 수 있습니다. 그런데 함수 내부에서 무조건 `User`를 반환하면 타입이 맞지 않습니다.

반면 아래 코드는 가능합니다.

```swift
func makeUser() -> some UserRepresentable {
    User(name: "min")
}
```

`some UserRepresentable`은 함수 구현부가 하나의 concrete type을 정하고, 외부에는 감춰서 반환하는 방식입니다.

면접 답변 예시:

> Generic 반환 타입의 `T`는 호출자가 결정하는 타입입니다. 따라서 `func makeUser<T>() -> T`는 호출자가 어떤 `T`를 요구하든 그 타입을 반환할 수 있어야 합니다. 반면 `some Protocol`은 함수 구현부가 하나의 concrete type을 정하고 외부에 숨기는 opaque return type이므로 `User`를 고정 반환할 수 있습니다.

---

## 8. associatedtype이 있는 Protocol

```swift
protocol Repository {
    associatedtype Entity

    func fetch() -> Entity
}
```

`associatedtype`은 protocol을 채택하는 concrete type마다 달라질 수 있는 타입입니다.

```swift
struct UserRepository: Repository {
    func fetch() -> User {
        User(name: "min")
    }
}

struct ProductRepository: Repository {
    func fetch() -> Product {
        Product()
    }
}
```

여기서:

- `UserRepository.Entity == User`
- `ProductRepository.Entity == Product`

입니다.

그런데 아래처럼 쓰면 문제가 생깁니다.

```swift
let repository: any Repository
let result = repository.fetch()
```

`any Repository`만 보면 `Entity`가 `User`인지, `Product`인지 컴파일러가 정확히 알 수 없습니다. 즉 concrete type 정보가 existential container 안으로 숨겨지면서 associated type 정보도 안전하게 다루기 어려워집니다.

### Generic으로 받으면 associatedtype 정보가 보존된다

```swift
func load<R: Repository>(_ repository: R) {
    let entity = repository.fetch()
}
```

이 경우 `R`이 `UserRepository`라면 `R.Entity == User`라는 정보가 유지됩니다.

### any로 받으면 associatedtype 정보가 약해진다

```swift
func load(_ repository: any Repository) {
    let entity = repository.fetch()
}
```

이 경우 `repository`가 어떤 concrete type인지 모르기 때문에 `Entity`를 구체 타입처럼 다루기 어렵습니다.

면접 답변 예시:

> Generic으로 받으면 concrete type이 유지되기 때문에 associatedtype 정보도 함께 보존됩니다. 반면 `any Repository`로 받으면 existential container에 담기면서 concrete type 정보가 추상화됩니다. 이때 `Entity`가 어떤 타입인지 컴파일러가 명확히 알 수 없으므로 associatedtype을 사용하는 메서드를 구체 타입처럼 다루기 어렵습니다.

---

## 9. Heterogeneous Collection과 associatedtype 문제

```swift
protocol Container {
    associatedtype Item

    var items: [Item] { get }
}

struct IntContainer: Container {
    let items: [Int]
}

struct StringContainer: Container {
    let items: [String]
}
```

서로 다른 `Item` 타입을 가진 컨테이너를 배열에 담을 수 있습니다.

```swift
let containers: [any Container] = [
    IntContainer(items: [1, 2, 3]),
    StringContainer(items: ["a", "b"])
]
```

하지만 `containers[0].items`를 안전하게 다루기 어렵습니다.

왜냐하면 배열의 원소 타입은 모두 `any Container`이고, 각 원소의 실제 `Item` 타입은 다를 수 있기 때문입니다.

```swift
let first = containers[0]
// first.items는 [Int]인가? [String]인가?
```

컴파일러는 `Item` 타입을 정적으로 보장하기 어렵습니다.

해결 방향은 보통 세 가지입니다.

1. Generic으로 `Item`을 고정한다
2. 가능한 타입이 정해져 있다면 enum으로 감싼다
3. Type Erasure wrapper를 만든다

---

## 10. Type Erasure

Type Erasure는 **구체 타입 정보를 외부 API에서 숨기고, 하나의 wrapper 타입으로 감싸는 기법**입니다.

대표 예시는 다음과 같습니다.

- `AnySequence<Element>`
- `AnyPublisher<Output, Failure>`
- `AnyHashable`

중요한 점은, Type Erasure가 모든 타입 정보를 지우는 것이 아니라는 점입니다.

```swift
AnyPublisher<User, Error>
```

여기서 유지되는 정보:

- `Output == User`
- `Failure == Error`

지워지는 정보:

- 내부 publisher의 구체 타입
- 예: `URLSession.DataTaskPublisher`, `Map`, `Decode`, `FlatMap` 등이 조합된 복잡한 실제 타입

### Combine 예시

```swift
func fetchUser() -> AnyPublisher<User, Error> {
    URLSession.shared.dataTaskPublisher(for: url)
        .map(\.data)
        .decode(type: User.self, decoder: JSONDecoder())
        .eraseToAnyPublisher()
}
```

외부에서는 내부 구현이 `URLSession`인지, `Just`인지, `Future`인지 알 필요가 없습니다. 단지 `User`를 방출하고 실패 시 `Error`를 방출한다는 사실만 알면 됩니다.

### some Publisher와 AnyPublisher의 차이

```swift
func fetchUser() -> some Publisher
```

`some Publisher`는 opaque return type입니다. 외부에 concrete type을 숨기지만, 함수 내부에서는 항상 하나의 concrete publisher 타입으로 고정되어야 합니다.

```swift
func fetchUser() -> AnyPublisher<User, Error>
```

`AnyPublisher<User, Error>`는 type erasure입니다. 내부 concrete publisher 타입을 숨기고, 외부에는 `Output`, `Failure`만 명확히 노출합니다.

조건에 따라 서로 다른 publisher를 반환해야 할 때 `AnyPublisher`가 편합니다.

```swift
func fetchUser(useCache: Bool) -> AnyPublisher<User, Error> {
    if useCache {
        return Just(User(name: "cache"))
            .setFailureType(to: Error.self)
            .eraseToAnyPublisher()
    } else {
        return networkPublisher
            .eraseToAnyPublisher()
    }
}
```

면접 답변 예시:

> Type Erasure는 구체 타입 정보를 외부에 노출하지 않기 위해 프로토콜을 만족하는 concrete type을 하나의 wrapper 타입으로 감싸는 기법입니다. `associatedtype`이나 `Self requirement`가 있는 protocol은 existential로 다루기 어려울 수 있는데, Type Erasure를 사용하면 중요한 타입 정보는 generic parameter로 유지하면서 내부 concrete type은 숨길 수 있습니다.

---

## 11. Self Requirement와 Equatable 문제

## Self requirement란?

```swift
protocol Copyable {
    func copy() -> Self
}
```

여기서 `Self`는 protocol 자체가 아니라 **이 protocol을 채택한 concrete type 자기 자신**을 의미합니다.

```swift
struct Document: Copyable {
    func copy() -> Document {
        self
    }
}

struct ImageFile: Copyable {
    func copy() -> ImageFile {
        self
    }
}
```

`Document` 입장에서는 `Self == Document`, `ImageFile` 입장에서는 `Self == ImageFile`입니다.

그런데 아래 코드는 다루기 어렵습니다.

```swift
let value: any Copyable = Document()
let copied = value.copy()
```

`value` 안에는 `Document`가 있을 수도 있고 `ImageFile`이 있을 수도 있습니다. `copy()`는 실제 concrete type과 같은 타입을 반환해야 하는데, existential 밖에서는 그 concrete type을 알기 어렵습니다.

### Equatable도 Self requirement를 가진다

`Equatable`의 핵심 요구사항은 개념적으로 아래와 같습니다.

```swift
protocol Equatable {
    static func == (lhs: Self, rhs: Self) -> Bool
}
```

즉, 같은 concrete type끼리 비교해야 합니다.

```swift
func compare<T: Equatable>(_ lhs: T, _ rhs: T) -> Bool {
    lhs == rhs
}
```

이 코드는 안전합니다. `lhs`와 `rhs`가 반드시 같은 `T` 타입이기 때문입니다.

하지만 아래 코드는 문제가 됩니다.

```swift
func compare(_ lhs: any Equatable, _ rhs: any Equatable) -> Bool {
    // lhs == rhs // ❌ 타입 안전하게 비교하기 어려움
    false
}
```

둘 다 `any Equatable`이지만 내부 concrete type은 다를 수 있습니다.

```swift
let lhs: any Equatable = 1
let rhs: any Equatable = "1"
```

`Int == String`은 불가능합니다. 그래서 `any Equatable`끼리는 단순히 `==`를 호출하기 어렵고, `AnyHashable`이나 커스텀 Type Erasure wrapper가 필요할 수 있습니다.

면접 답변 예시:

> `Self`는 protocol 자체가 아니라 해당 protocol을 채택한 concrete type을 의미합니다. `Equatable`의 `==`도 `Self`끼리 비교해야 하므로 같은 concrete type임이 보장되어야 합니다. Generic은 `T`가 하나로 고정되기 때문에 안전하지만, `any Equatable` 두 개는 내부 타입이 다를 수 있어 `==`를 바로 호출하기 어렵습니다.

---

## 12. Generic Constraint와 where clause

Generic에서는 `where` clause로 더 구체적인 조건을 줄 수 있습니다.

```swift
func printAll<C: Collection>(_ collection: C) where C.Element == String {
    collection.forEach {
        print($0)
    }
}
```

이 함수는 다음 조건을 의미합니다.

- `C`는 `Collection`이어야 한다
- `C.Element`는 반드시 `String`이어야 한다

그래서 아래는 가능합니다.

```swift
printAll(["a", "b", "c"])
```

하지만 아래는 불가능합니다.

```swift
// printAll([1, 2, 3]) // ❌ Element가 Int
```

`where` clause는 associatedtype이 있는 protocol을 다룰 때 특히 유용합니다.

```swift
func compareElements<A: Collection, B: Collection>(
    _ a: A,
    _ b: B
) where A.Element == B.Element, A.Element: Equatable {
    // 두 컬렉션의 Element 타입이 같고 Equatable일 때만 가능
}
```

> 면접 포인트: `where`는 단순히 `T: Protocol` 이상으로, associatedtype의 타입 일치나 추가 protocol 채택 조건을 표현할 때 사용합니다.

---

## 13. Protocol Composition

Protocol Composition은 여러 프로토콜 또는 클래스 제약을 조합해서 하나의 타입 조건처럼 사용하는 방식입니다.

```swift
protocol Configurable {
    func configure()
}

protocol Trackable {
    func track()
}

func configure(_ view: UIView & Configurable & Trackable) {
    view.configure()
    view.track()
}
```

이 함수의 의미는 다음과 같습니다.

> `view`는 `UIView`의 하위 타입이면서, 동시에 `Configurable`과 `Trackable`을 모두 만족해야 한다.

Generic으로 표현하면 아래처럼 쓸 수도 있습니다.

```swift
func configure<T>(_ view: T) where T: UIView, T: Configurable, T: Trackable {
    view.configure()
    view.track()
}
```

### 장점

필요한 역할만 조합해서 요구할 수 있습니다.

```swift
UIView & Configurable & Trackable
```

함수가 요구하는 조건이 명확합니다.

### 단점

조합이 많아지면 타입 시그니처가 복잡해지고, 하나의 객체에 너무 많은 역할을 요구하게 될 수 있습니다.

```swift
UIView & Configurable & Trackable & Reusable & Bindable
```

이 정도로 길어지면 설계를 다시 점검해볼 필요가 있습니다.

---

## 14. Generics와 Specialization

Generics는 여러 타입에 대해 동작하는 코드를 한 번만 작성하는 기법입니다.

```swift
func swapValues<T>(_ a: inout T, _ b: inout T) {
    let temp = a
    a = b
    b = temp
}
```

### Generic Specialization

Generic Specialization은 제네릭 함수가 실제 concrete type으로 호출될 때, 컴파일러가 해당 타입에 맞는 전용 구현처럼 최적화하는 과정입니다.

```swift
func printValue<T>(_ value: T) {
    print(value)
}

printValue(10)
printValue("hello")
```

컴파일러는 최적화 과정에서 개념적으로 아래처럼 처리할 수 있습니다.

```swift
func printValue_Int(_ value: Int) {
    print(value)
}

func printValue_String(_ value: String) {
    print(value)
}
```

장점은 다음과 같습니다.

- concrete type 기준으로 최적화 가능
- 인라인 최적화 가능
- witness table / existential container 비용 감소
- `any Protocol`보다 성능상 유리할 수 있음

단, generic을 쓴다고 항상 specialization이 보장되는 것은 아닙니다. 모듈 경계, 최적화 옵션, 코드 크기 증가 가능성 때문에 컴파일러가 전용 코드를 만들지 않을 수 있습니다.

### @inlinable

다른 모듈의 public generic 함수는 호출 모듈에서 함수 본문을 볼 수 없어 specialization이 제한될 수 있습니다. `@inlinable`을 붙이면 함수 본문이 모듈 인터페이스에 노출되어 호출 쪽에서 최적화할 수 있습니다.

```swift
@inlinable
public func processItems<T>(_ items: [T]) -> Int {
    items.count
}
```

Trade-off:

- 장점: 모듈 경계를 넘어 specialization 가능
- 단점: 바이너리 크기 증가, 구현 노출, ABI 안정성 제약

> 면접 포인트: Generic은 concrete type 정보를 유지하기 때문에 specialization과 inline 최적화에 유리합니다. 하지만 모듈 경계에서는 `@inlinable` 같은 추가 고려가 필요합니다.

---

## 15. 실무 선택 기준: Concrete vs Generic vs any

아래 세 함수를 기준으로 선택 기준을 정리할 수 있습니다.

```swift
func run(_ service: UserService)
```

```swift
func run<T: UserServiceProtocol>(_ service: T)
```

```swift
func run(_ service: any UserServiceProtocol)
```

### 1) Concrete Type

```swift
func run(_ service: UserService)
```

구현체가 하나이고 다형성이 필요 없다면 concrete type을 선택합니다.

장점:

- 가장 단순함
- 코드 추적이 쉬움
- 불필요한 protocol을 만들지 않아도 됨

### 2) Generic

```swift
func run<T: UserServiceProtocol>(_ service: T)
```

여러 구현체를 받을 수 있어야 하지만 타입 정보를 보존해야 할 때 선택합니다.

적합한 경우:

- 타입 관계를 유지해야 함
- associatedtype / Self requirement가 중요함
- 성능 최적화가 중요함
- `T`를 파라미터, 반환 타입, 내부 타입과 연결해야 함

### 3) Existential

```swift
func run(_ service: any UserServiceProtocol)
```

구체 타입을 숨기고 런타임 다형성이 필요할 때 선택합니다.

적합한 경우:

- 서로 다른 구현체를 하나의 배열에 담아야 함
- API 경계에서 구체 타입을 숨기고 싶음
- 타입 관계가 중요하지 않고 protocol requirement만 호출하면 됨

```swift
let services: [any UserServiceProtocol] = [
    RealUserService(),
    MockUserService(),
    CachedUserService()
]
```

최종 기준:

> Concrete type을 기본으로 두고, 타입 관계와 성능이 중요하면 Generic이나 `some`을 사용하고, 런타임 다형성이나 heterogeneous collection이 필요하면 `any`를 선택합니다.

---

## 16. POP를 실무에서 남용하면 생기는 문제

POP가 항상 좋은 것은 아닙니다. 모든 타입에 protocol을 만들면 오히려 추상화 비용이 커질 수 있습니다.

```swift
protocol UserServiceType {}
protocol UserServiceProtocol {}
protocol UserRepresentable {}
```

### 문제점

1. 구현체가 하나뿐인데 protocol이 생겨 코드 이동이 많아짐
2. 비슷한 역할의 protocol이 중복됨
3. 실제 동작을 추적하기 어려워짐
4. `associatedtype`, `some`, `any`, type erasure가 섞이면 에러 메시지와 디버깅이 어려워짐
5. `any Protocol`을 남용하면 existential container와 witness table dispatch 비용이 생길 수 있음

면접 답변 예시:

> POP는 역할을 protocol로 분리하고 조합할 수 있다는 장점이 있지만, 모든 타입에 무조건 protocol을 만들면 추상화 비용이 커질 수 있습니다. 구현체가 하나뿐인데 protocol을 만들면 코드 추적이 어려워지고, 비슷한 protocol이 중복되면 설계 경계가 흐려집니다. 그래서 protocol은 다형성, 테스트 대역, 모듈 간 의존성 분리처럼 명확한 이유가 있을 때 도입하는 것이 좋습니다.

핵심 문장:

> **Protocol은 가능해서 만드는 게 아니라, 역할 분리와 다형성이 필요할 때 만든다.**

---

## 💬 꼬리 질문 & 면접 답변

### Q1. Protocol Oriented Programming이 뭔가요?

Protocol Oriented Programming은 class 상속보다 protocol을 중심으로 역할과 요구사항을 정의하는 설계 방식입니다. Swift에서는 struct, enum, class 모두 protocol을 채택할 수 있어서 value type 기반 설계에서도 다형성을 사용할 수 있습니다. 또한 protocol extension으로 기본 구현을 제공해 상속 없이 코드 재사용과 기능 조합이 가능합니다.

---

### Q2. protocol과 protocol extension의 차이는?

`protocol`은 타입이 반드시 만족해야 하는 요구사항을 정의합니다. `protocol extension`은 그 요구사항에 대한 기본 구현이나 공통 기능을 제공합니다. 다만 protocol과 protocol extension 모두 저장 프로퍼티는 가질 수 없고, computed property 기본 구현만 가능합니다.

---

### Q3. protocol extension 메서드가 override되지 않는 경우는?

protocol requirement에 선언되지 않은 extension 전용 메서드입니다. 이 메서드는 witness table에 등록되지 않기 때문에 `any Protocol` 타입으로 호출하면 concrete type의 동일한 이름 메서드가 있어도 extension 기본 구현이 호출될 수 있습니다. 진짜 다형적으로 호출하려면 protocol 본문에 requirement로 선언해야 합니다.

---

### Q4. some과 any의 차이를 한 줄로 설명한다면?

`some`은 컴파일 타임에 하나의 concrete type으로 고정되는 opaque type이고, `any`는 런타임에 여러 concrete type을 담을 수 있는 existential type입니다.

---

### Q5. 함수 파라미터에서 generic과 some Protocol은 같은가요?

단일 파라미터에서는 거의 generic의 축약 문법처럼 볼 수 있습니다. 하지만 generic은 `T`를 여러 위치에서 재사용해 타입 관계를 표현할 수 있습니다. 반면 각각의 `some Protocol` 파라미터는 독립적인 opaque parameter로 취급됩니다.

---

### Q6. `func makeUser<T>() -> T`에서 내부에서 `User()`를 반환하면 왜 문제가 되나요?

Generic 반환 타입의 `T`는 호출자가 결정합니다. 호출자가 `Admin`을 기대할 수도 있는데 함수 내부에서 무조건 `User`를 반환하면 타입이 맞지 않습니다. 반면 `some UserRepresentable`은 함수 구현부가 하나의 concrete type을 정하고 외부에 숨기는 방식이므로 `User`를 고정 반환할 수 있습니다.

---

### Q7. `some Animal`에서 조건에 따라 `Dog`, `Cat`을 반환하면 왜 안 되나요?

`some Animal`은 `Animal`을 만족하는 아무 타입이나 반환한다는 뜻이 아니라, 하나의 concrete type을 숨긴다는 뜻입니다. 따라서 모든 return path에서 같은 concrete type을 반환해야 합니다. 조건에 따라 다른 타입을 반환해야 하면 `any Animal` 또는 enum wrapper를 사용해야 합니다.

---

### Q8. associatedtype이 있는 protocol은 왜 existential로 쓰기 어렵나요?

associatedtype은 protocol을 채택하는 concrete type마다 달라질 수 있습니다. `any Repository`처럼 existential로 감싸면 concrete type이 지워지고 `Entity`가 무엇인지 컴파일러가 알기 어려워집니다. 그래서 associatedtype 정보가 중요한 API에서는 generic constraint를 선호합니다.

---

### Q9. Generic으로 받는 것과 `any Protocol`로 받는 것의 차이는?

Generic은 concrete type 정보와 associatedtype 정보를 보존합니다. 그래서 타입 안정성과 최적화에 유리합니다. 반면 `any Protocol`은 existential container에 담기면서 concrete type 정보가 숨겨지고, witness table dispatch가 필요할 수 있습니다.

---

### Q10. Type Erasure가 뭔가요?

Type Erasure는 concrete type 정보를 외부에 노출하지 않기 위해 wrapper 타입으로 감싸는 기법입니다. `AnyPublisher<User, Error>`는 `Output == User`, `Failure == Error` 정보는 유지하면서 내부 publisher의 복잡한 concrete type은 숨깁니다.

---

### Q11. `some Publisher`와 `AnyPublisher<User, Error>`의 차이는?

`some Publisher`는 opaque return type으로 외부에 concrete type을 숨기지만, 함수 내부에서는 하나의 concrete publisher 타입으로 고정되어야 합니다. `AnyPublisher<User, Error>`는 type erasure를 통해 내부 publisher 타입을 숨기고 외부에는 `User`와 `Error` 타입 정보만 명확히 노출합니다. 조건에 따라 서로 다른 publisher를 반환해야 하면 `AnyPublisher`가 실무적으로 편합니다.

---

### Q12. `Self requirement`가 있는 protocol은 왜 existential에서 까다로운가요?

`Self`는 protocol 자체가 아니라 해당 protocol을 채택한 concrete type을 의미합니다. `func copy() -> Self`는 실제 concrete type과 같은 타입을 반환해야 하는데, `any Copyable`로 감싸면 외부에서는 그 concrete type을 알기 어렵습니다.

---

### Q13. `any Equatable`끼리 `==`가 어려운 이유는?

`Equatable`의 `==`는 `Self`끼리 비교해야 합니다. Generic의 `T: Equatable`은 두 값이 같은 `T` 타입임을 보장하지만, `any Equatable` 두 개는 내부 concrete type이 서로 다를 수 있습니다. 따라서 `any Equatable`끼리는 단순히 `==`를 호출하기 어렵고, `AnyHashable` 같은 wrapper가 필요할 수 있습니다.

---

### Q14. where clause는 언제 사용하나요?

Generic 타입에 더 구체적인 제약을 걸 때 사용합니다. 예를 들어 `C: Collection where C.Element == String`은 Collection이면서 Element가 String인 타입만 허용한다는 뜻입니다. associatedtype의 타입 일치나 추가 protocol 제약을 표현할 때 유용합니다.

---

### Q15. Protocol Composition이 뭔가요?

여러 프로토콜 또는 클래스 제약을 조합해 하나의 타입 조건처럼 사용하는 방식입니다. 예를 들어 `UIView & Configurable & Trackable`은 UIView 하위 타입이면서 Configurable과 Trackable을 모두 만족해야 한다는 뜻입니다. 필요한 역할만 조합할 수 있지만, 너무 많아지면 타입 시그니처가 복잡해지고 설계가 무거워질 수 있습니다.

---

### Q16. Generic Specialization이 뭔가요?

Generic 함수가 실제 concrete type으로 호출될 때 컴파일러가 해당 타입에 맞는 전용 구현처럼 최적화하는 과정입니다. 예를 들어 `printValue<T>`가 `Int`, `String`으로 호출되면 각각의 타입에 맞게 최적화할 수 있습니다. 이로 인해 인라이닝과 static dispatch에 가까운 최적화가 가능해집니다.

---

### Q17. POP를 남용하면 어떤 문제가 생기나요?

불필요한 protocol이 많아져 코드 추적이 어려워지고, 비슷한 역할의 protocol이 중복될 수 있습니다. 구현체가 하나뿐인데 protocol을 만들면 추상화 비용만 증가합니다. 따라서 protocol은 다형성, 테스트 대역, 모듈 간 의존성 분리처럼 명확한 이유가 있을 때 도입하는 것이 좋습니다.

---

### Q18. Concrete Type, Generic, any Protocol은 어떻게 선택하나요?

구현체가 하나이고 추상화가 필요 없으면 concrete type을 사용합니다. 여러 구현체를 받을 수 있어야 하면서 타입 정보와 성능이 중요하면 generic을 사용합니다. 구체 타입을 숨기고 런타임 다형성이나 heterogeneous collection이 필요하면 `any Protocol`을 사용합니다.

---

## ✏️ 퀴즈

### 문제 1

protocol extension에 정의된 메서드가 Witness Table에 등록되려면?

- A. extension에 정의하기만 하면 자동 등록된다
- B. protocol 본문에 requirement로 선언해야 한다
- C. @objc 또는 dynamic 키워드를 붙여야 한다
- D. final 키워드를 붙여야 한다

**정답: B**

---

### 문제 2

다음 중 가장 빠른 dispatch는?

- A. Static Dispatch
- B. V-Table Dispatch
- C. Witness Table Dispatch
- D. Message Dispatch

**정답: A**

---

### 문제 3

`some Shape`와 `any Shape`의 가장 큰 차이는?

- A. some은 protocol이고 any는 class다
- B. some은 컴파일 타임 고정, any는 런타임 결정
- C. some은 빠르고 any는 항상 같은 속도다
- D. 둘은 완전히 동일하다

**정답: B**

---

### 문제 4

아래 코드는 왜 컴파일되지 않을 가능성이 높은가?

```swift
func makeAnimal(_ isDog: Bool) -> some Animal {
    if isDog {
        return Dog()
    } else {
        return Cat()
    }
}
```

- A. `some`은 class에서만 쓸 수 있기 때문
- B. `some Animal`은 모든 return path에서 같은 concrete type이어야 하기 때문
- C. `Dog`와 `Cat`이 value type이기 때문
- D. protocol은 return type으로 쓸 수 없기 때문

**정답: B**

---

### 문제 5

아래 함수에서 `T`는 누가 결정하는가?

```swift
func makeValue<T: UserRepresentable>() -> T
```

- A. 함수 내부 구현부
- B. 호출자 / 호출 문맥
- C. protocol extension
- D. 런타임의 witness table

**정답: B**

---

### 문제 6

`any Equatable` 두 개를 바로 `==`로 비교하기 어려운 이유는?

- A. Equatable은 class 전용 protocol이기 때문
- B. `==`가 `Self` requirement를 가지며, 두 existential의 concrete type이 같다는 보장이 없기 때문
- C. Equatable은 Swift에서 deprecated 되었기 때문
- D. any는 항상 nil이 될 수 있기 때문

**정답: B**

---

### 문제 7

Type Erasure가 지우는 것은 무엇에 가장 가까운가?

- A. 모든 타입 정보
- B. 내부 concrete type 정보
- C. Output과 Failure 정보
- D. protocol requirement 정보

**정답: B**

---

### 문제 8

`where C.Element == String`의 의미는?

- A. C가 반드시 String이어야 한다
- B. C가 Collection이고 Element가 String이어야 한다
- C. C가 class여야 한다
- D. C가 optional이어야 한다

**정답: B**

---

## 🧩 최종 면접용 요약

면접에서 길게 설명하기 어렵다면 아래 흐름으로 답하면 됩니다.

> Swift의 POP는 protocol로 역할을 정의하고 protocol extension으로 기본 구현을 제공해 상속보다 조합을 중시하는 설계 방식입니다. 다만 protocol을 existential로 사용할 경우 concrete type 정보가 지워지고 witness table dispatch가 발생할 수 있습니다. 성능과 타입 관계가 중요하면 generic이나 `some`을 사용하고, 런타임 다형성이나 서로 다른 타입을 하나의 컬렉션에 담아야 하면 `any`를 사용합니다. 특히 associatedtype이나 Self requirement가 있는 protocol은 existential로 다루기 어려우므로 generic constraint나 type erasure를 고려해야 합니다.

---

## ✅ 오늘 반드시 기억할 문장

1. `protocol`은 요구사항, `protocol extension`은 기본 구현이다.
2. protocol extension 메서드가 requirement가 아니면 witness table에 들어가지 않는다.
3. `some`은 하나의 concrete type을 숨기는 것이고, `any`는 여러 concrete type을 담을 수 있는 existential이다.
4. Generic의 `T`는 보통 호출자가 결정한다.
5. associatedtype 정보가 중요하면 `any`보다 generic이 유리하다.
6. Type Erasure는 내부 concrete type을 숨기고 외부 API를 단순화한다.
7. `Self`는 protocol 자체가 아니라 채택한 concrete type이다.
8. POP는 가능해서 쓰는 게 아니라, 역할 분리와 다형성이 필요할 때 쓴다.
