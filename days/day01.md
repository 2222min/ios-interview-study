# Day 1 — Value vs Reference / Copy-on-Write

**태그**: struct · class · Stack · Heap · Copy-on-Write · Existential Container

---

## 📝 핵심 정리


### 1. Value Type vs Reference Type 기본 개념

_아이콘: `blue`_


### Value Type과 Reference Type의 차이가 뭔가요?

가장 큰 차이는 **"복사할 때 일어나는 일"**입니다.

### Value Type (struct, enum)

```swift
struct Point {
    var x: Int
    var y: Int
}

var a = Point(x: 1, y: 2)
var b = a       // 값 복사! a와 b는 완전히 별개
b.x = 100

print(a.x)  // 1 (a는 그대로)
print(b.x)  // 100 (b만 변경)
```

### Reference Type (class)

```swift
class Person {
    var age: Int
    init(age: Int) { self.age = age }
}

var a = Person(age: 30)
var b = a       // 참조 복사! a와 b는 같은 객체를 가리킴
b.age = 100

print(a.age)  // 100 (a도 같이 변경됨!)
print(b.age)  // 100
```

### 왜 이런 차이가 나나요?

값 타입은 변수 자체가 데이터를 담고 있고, 참조 타입은 변수가 데이터의 "주소(포인터)"를 담고 있기 때문입니다.

```swift
// Value Type 메모리:
// var a = Point(x:1, y:2)
// 스택: [a: x=1, y=2]  ← 값이 직접 저장됨
//
// var b = a
// 스택: [a: x=1, y=2]
//       [b: x=1, y=2]  ← 별개의 영역에 복사됨

// Reference Type 메모리:
// var a = Person(age:30)
// 스택: [a: ──┐] (포인터)
//             ▼
// 힙:   ┌─────────────┐
//       │ Person      │
//       │ age: 30     │
//       └─────────────┘
//
// var b = a
// 스택: [a: ──┐] [b: ──┐] (둘 다 같은 곳을 가리킴)
//             ▼     ▼
// 힙:   ┌─────────────┐
//       │ Person      │
//       │ age: 30     │
//       └─────────────┘
```

### 그럼 언제 struct, 언제 class를 써야 하나요?

Apple의 공식 가이드라인:

| 상황 | 선택 |
|---|---|
| 기본 (대부분의 경우) | **struct** |
| 정체성(identity)이 중요할 때 (=== 비교) | **class** |
| 상속이 필요할 때 | **class** |
| 참조 공유가 의도된 동작일 때 | **class** |
| Objective-C 호환 필요 | **class (NSObject)** |
| deinit이 필요한 자원 관리 | **class** |

> 💡 **💡 면접 포인트:** Swift는 "value type 우선" 언어입니다. String, Array, Dictionary, Set 같은 핵심 타입들이 모두 struct로 구현되어 있죠. 값 타입은 thread-safety, predictability, 그리고 함수형 프로그래밍 친화성을 제공합니다. 단, 큰 데이터를 자주 복사하면 비용이 클 수 있어서 Copy-on-Write로 최적화합니다.


### 2. 메모리 레이아웃 차이 (Stack vs Heap)

_아이콘: `green`_


### Stack과 Heap이 뭔가요?

프로그램이 사용하는 메모리 영역의 두 종류입니다.

| 항목 | Stack | Heap |
|---|---|---|
| **할당 속도** | 매우 빠름 (포인터 +/-) | 느림 (malloc 호출) |
| **해제** | 함수 종료 시 자동 | ARC가 관리 |
| **크기 제한** | 제한적 (~MB 단위) | 큼 (~GB 단위) |
| **스레드** | 스레드별 별도 | 공유 (lock 필요) |

### struct는 Stack? class는 Heap?

일반화하면 그렇지만 정확하진 않습니다. **"struct는 보통 인라인으로 저장되고, class는 항상 힙에 저장된다"**가 정확합니다.

### 실제 메모리 크기 비교

```swift
// 같은 데이터인데 struct vs class
struct PointS {
    var x: Double  // 8 bytes
    var y: Double  // 8 bytes
}
// → 총 16 bytes, 스택에 인라인 저장

class PointC {
    var x: Double  // 8 bytes
    var y: Double  // 8 bytes
}
// 힙 할당:
//   metadata 포인터: 8 bytes
//   refCount: 8 bytes
//   x: 8 bytes
//   y: 8 bytes
// → 32 bytes (struct의 2배)
// + 스택의 포인터: 8 bytes
// + malloc overhead: ~16 bytes
// 실질적 비용: ~56 bytes (struct의 3.5배!)
```

### struct가 항상 스택에 가는 건 아니에요

아래 경우에는 struct도 힙에 저장됩니다:

- **Existential Container에 담긴 큰 struct**: 24 bytes 초과 시 힙

- **클로저에 캡처된 변수**: closure context는 힙

- **Generic 컨텍스트 (specialization 안 됐을 때)**

- **Indirect enum case**

### 성능 비교 (실측 기준)

- struct 복사: ~1ns (스택 memcpy)

- class retain: ~5-10ns (atomic increment)

- class 힙 할당: ~50-100ns (malloc 호출)

- struct 힙 할당 (existential): ~50-100ns

> 💡 **💡 면접 포인트:** "struct는 인라인 저장이라 메모리 효율이 좋고, 할당/해제가 빠릅니다. class는 항상 힙 할당이라 추가 오버헤드가 있지만, 참조로 전달하면 큰 데이터도 빠르게 공유할 수 있죠. 핵심 라이브러리(Array, Dictionary)는 struct이지만 내부에 reference type 버퍼를 가져 Copy-on-Write로 두 마리 토끼를 잡습니다."


### 3. Existential Container (프로토콜 타입의 비밀)

_아이콘: `purple`_


### Existential이 뭔가요?

"존재하는 어떤 타입"을 의미합니다. 프로토콜을 변수 타입으로 사용할 때 그 변수의 정체가 바로 existential입니다.

```swift
protocol Animal {
    func makeSound()
}

struct Dog: Animal { ... }
struct Cat: Animal { ... }

let pet: Animal = Dog()  // ← 이게 existential
// 'Animal' 자체는 타입이 아니라 프로토콜이지만,
// 'Animal'을 채택한 어떤 구체 타입이든 담을 수 있는 컨테이너 역할을 합니다.
```

### Existential Container 내부 구조

이런 변수는 단순 포인터가 아닙니다. 다음 5개의 워드(64비트 시스템에서 8바이트씩)를 담는 박스입니다:

```swift
// Existential Container = 5 words = 40 bytes
//
// ┌─────────────────────────────────┐
// │  Inline Value Buffer (24 bytes) │  ← 작은 값은 여기에 직접 저장
// ├─────────────────────────────────┤
// │  Value Witness Table ptr (8B)   │  ← 복사/소멸/크기 함수 테이블
// ├─────────────────────────────────┤
// │  Protocol Witness Table ptr (8B)│  ← 프로토콜 메서드 테이블
// └─────────────────────────────────┘
```

### Inline Value Buffer (24 bytes 룰)

값의 크기가 24바이트(3 words) 이하면 buffer에 직접 저장됩니다. 초과하면 힙 할당 후 포인터만 buffer에 저장됩니다.

```swift
// 작은 struct → 인라인 저장 (힙 할당 없음, 빠름)
struct Small: Animal {
    var x: Int  // 8 bytes
    var y: Int  // 8 bytes
    func makeSound() { print("작음") }
}
let pet1: Animal = Small(x:1, y:2)
// Inline buffer에 그대로 저장 → 빠름

// 큰 struct → 힙 할당 (느림)
struct Large: Animal {
    var x: Int      // 8B
    var y: Int      // 8B
    var z: Int      // 8B
    var w: Int      // 8B
    var v: Int      // 8B (총 40B)
    func makeSound() { print("큼") }
}
let pet2: Animal = Large(x:1, y:2, z:3, w:4, v:5)
// 24B 초과 → 힙에 Large 할당 → buffer엔 힙 포인터만
```

### Value Witness Table (VWT)

"이 타입을 어떻게 다뤄야 하는지"에 대한 함수 테이블입니다.

- `size`: 이 타입의 크기는?

- `copy`: 어떻게 복사하지?

- `destroy`: 어떻게 메모리 해제하지?

- `equals`: 어떻게 비교하지?

제네릭 컨텍스트에서 컴파일러가 구체 타입을 모를 때 이 테이블을 통해 런타임에 처리합니다.

### Protocol Witness Table (PWT)

"이 타입이 프로토콜의 메서드를 어떻게 구현했는지"에 대한 테이블입니다.

```swift
// 컴파일러가 자동 생성:
// Dog의 Animal PWT:
//   makeSound 함수 포인터 → Dog.makeSound 구현체

// 호출 시:
let pet: Animal = Dog()
pet.makeSound()
// 1. existential container의 PWT 포인터 따라가기
// 2. PWT[0] (makeSound 슬롯)에서 함수 포인터 가져오기
// 3. 그 함수 호출 → Dog.makeSound 실행
// → 간접 호출 발생 (성능 비용)
```

### 왜 이렇게 복잡하게 만들었나요?

"어떤 타입이든 담을 수 있는 변수"를 만들려면 컴파일 타임에 타입을 알 수 없습니다. 그래서 런타임에 필요한 모든 정보를 컨테이너에 함께 담고 다니는 거죠. 대가는 약간의 메모리와 간접 호출 오버헤드입니다.

> 💡 **💡 면접 포인트:** "프로토콜 타입(any Protocol)은 Existential Container라는 5워드 박스로 표현됩니다. 24바이트 이하의 값은 인라인 저장되어 빠르고, 초과하면 힙 할당이 발생합니다. Witness Table을 통한 dynamic dispatch가 일어나기 때문에 some Protocol(opaque type)이나 generic을 쓰면 static dispatch로 더 빠릅니다. 모듈 인터페이스에선 any로 유연성을 확보하고, 성능 중요 코드에선 some으로 최적화하는 게 일반적입니다."


### 4. Copy-on-Write (COW) 내부 동작

_아이콘: `orange`_


### COW가 뭔가요?

"복사 시 즉시 복사하지 않고, 실제 수정이 일어날 때만 복사한다"는 최적화 기법입니다.

### 왜 필요한가요?

Array 같은 큰 컬렉션이 struct(값 타입)면, 함수에 넘길 때마다 전체 복사가 일어나면 너무 비효율적입니다. 100만 개 원소를 가진 배열을 매번 복사하면 끔찍하죠.

```swift
var bigArray = [Int](repeating: 0, count: 1_000_000)
var copy = bigArray  // 만약 진짜 복사라면? → 1M × 8B = 8MB 복사!

// 하지만 실제로는 COW 덕분에 거의 즉시 끝남
// 둘이 같은 메모리를 공유하다가, 수정 시점에 비로소 복사
```

### Swift 표준 라이브러리의 COW

Array, Dictionary, Set, String이 모두 COW를 구현하고 있습니다. 이들은 struct이지만 내부에 **reference type 버퍼**를 가집니다.

```swift
// Array의 내부 구조 (단순화)
struct Array<Element> {
    var _buffer: _ArrayBuffer<Element>  // ← 이게 class!
}

// 동작 시나리오:
var a = [1, 2, 3]      // _buffer (refCount: 1)
var b = a              // 같은 _buffer 공유 (refCount: 2)
                       // ← 메모리 복사 없음! 빠름!

b.append(4)            
// 1. isKnownUniquelyReferenced(&_buffer) 확인
// 2. refCount > 1 → 다른 곳에서도 쓰고 있다!
// 3. 새 버퍼 할당 + 기존 데이터 복사
// 4. 새 버퍼에 4 추가
// 5. b._buffer = 새 버퍼 (refCount: 1)
// 6. a._buffer = 기존 버퍼 (refCount: 1)
```

### isKnownUniquelyReferenced

"이 참조를 가진 게 나뿐인가?"를 검사하는 함수입니다. COW 구현의 핵심이죠.

- true → 나만 쓰니까 직접 수정해도 안전

- false → 다른 곳도 쓰니까 복사 후 수정

### 커스텀 COW 구현하기

```swift
final class Storage<T> {
    var value: T
    init(_ value: T) { self.value = value }
}

struct COWWrapper<T> {
    private var storage: Storage<T>
    
    init(_ value: T) {
        storage = Storage(value)
    }
    
    var value: T {
        get { storage.value }
        set {
            // 핵심 로직!
            if isKnownUniquelyReferenced(&storage) {
                // 나만 참조 중 → 직접 수정 (복사 X)
                storage.value = newValue
            } else {
                // 다른 곳도 참조 중 → 새 storage 할당
                storage = Storage(newValue)
            }
        }
    }
}
```

### 주의사항

- **Storage는 반드시 final class**: ObjC 브릿지 클래스에는 isKnownUniquelyReferenced가 동작 안 함

- **thread-safe하지 않음**: 두 스레드가 동시에 수정하면 race condition 가능

### COW가 깨지는 흔한 실수

```swift
// ❌ 의도치 않은 복사 유발
func processArray(_ arr: inout [Int]) {
    let backup = arr      // refCount +1!
    arr.append(999)        // 다른 곳(backup)이 쓰니까 → 복사 발생!
    // backup이 살아있는 동안은 arr 수정 시 매번 복사
}

// ✅ 불필요한 참조 제거
func processArray(_ arr: inout [Int]) {
    arr.append(999)        // refCount == 1 → 복사 없이 직접 수정
}
```

### Small String Optimization

String도 COW를 쓰지만, 추가로 **15바이트 이하의 짧은 문자열은 힙 할당 없이 String 구조체 내부(16바이트)에 직접 저장**합니다. SSO(Small String Optimization)라고 부릅니다.

```swift
let s1 = "안녕"          // 6 bytes (UTF-8) → 인라인 저장 (힙 X)
let s2 = "Hello, World!" // 13 bytes → 인라인 저장 (힙 X)
let s3 = "긴 문자열... 16바이트 초과"  // → 힙 버퍼 + COW
```

> 💡 **💡 면접 포인트:** "Swift의 컬렉션 타입들은 struct이지만 내부에 reference type 버퍼를 두고 Copy-on-Write를 구현합니다. 덕분에 값 타입의 안전성(독립적 수정)과 참조 타입의 효율성(빠른 복사)을 동시에 얻죠. isKnownUniquelyReferenced로 유일 참조 여부를 검사하여 실제 복사 시점을 늦춥니다. 이 메커니즘 덕분에 [1...1_000_000]을 함수에 넘겨도 비용이 거의 없습니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. Swift에서 struct가 항상 스택에 저장되나요? `[기본 / 빈출]`

**아닙니다.** 일반적으로는 스택에 인라인 저장되지만, 다음 경우엔 힙에 저장됩니다:

1. **Existential Container에 담긴 큰 struct (24바이트 초과)**: 인라인 버퍼를 넘으면 힙 할당
2. **클로저에 캡처된 변수**: 클로저 컨텍스트는 힙에 있음
3. **Generic 컨텍스트 (specialization 실패 시)**: 컴파일러가 구체 타입을 모르면 힙
4. **Indirect enum case**: 재귀 enum은 힙 사용

그래서 \"struct = 스택\"은 정확하지 않고, 정확한 표현은 \"struct는 보통 인라인 저장\"입니다.


### Q2. Array를 함수 파라미터로 전달하면 복사되나요? `[기본 / 빈출]`

의미적으로는 복사지만, **Copy-on-Write 덕분에 실제 메모리 복사는 수정 시점까지 지연**됩니다.

함수 안에서 배열을 읽기만 하면 복사 비용 없음 (refCount만 +1). 수정하는 순간 비로소 복사가 일어납니다.

주의: `inout`으로 받으면 참조처럼 동작해서 원본을 직접 수정합니다. 복사 자체가 안 일어나죠.


### Q3. isKnownUniquelyReferenced가 ObjC 클래스에서 동작 안 하는 이유는? `[심화]`

이 함수는 Swift native class의 inline refCount를 검사하도록 설계되었습니다. ObjC 클래스는 다른 메모리 모델(NSObject 기반)을 사용하기 때문에 항상 false를 반환합니다.

그래서 커스텀 COW를 구현할 때 Storage 클래스는 반드시 `final class`(상속 불가)로 선언해야 합니다. 이래야 컴파일러가 Swift native class로 처리하고 정확한 검사가 가능합니다.


### Q4. any Protocol과 some Protocol의 성능 차이는? `[심화 / 빈출]`

**any (Existential)**: 런타임에 타입 결정. Existential Container와 Witness Table 통한 dynamic dispatch. 함수 호출 ~5-20ns.

**some (Opaque Type)**: 컴파일 타임에 구체 타입 결정. Static dispatch + 인라인 가능. 함수 호출 ~1ns.

차이가 크지 않아 보이지만 hot loop에서 누적되면 큽니다. SwiftUI body가 some View를 반환하는 이유도 이 때문입니다 — 컴파일러가 View 트리의 정확한 타입을 알아야 효율적인 diff가 가능하죠.

가이드: 모듈 경계에선 any로 유연성, 모듈 내부에선 some/generic으로 성능.


### Q5. struct 안에 class 프로퍼티가 있으면 어떻게 되나요? `[심화 / 빈출]`

struct를 복사할 때 class 프로퍼티는 **참조만 복사**됩니다 (shallow copy). 두 struct가 같은 class 인스턴스를 공유하게 되죠.

예시:

```swift
class Container { var value = 0 }\nstruct Wrapper { var box: Container }\n\nvar a = Wrapper(box: Container())\nvar b = a  // struct 복사\nb.box.value = 100\nprint(a.box.value)  // 100! (같은 Container 공유)
```
이걸 방지하려면 mutating setter에서 class를 deep copy해야 합니다. Array 같은 표준 타입은 COW로 자동 처리하지만, 직접 만든 struct는 수동 처리 필요.


---


## ✏️ 퀴즈


### 문제 1

다음 코드의 출력은?

```swift
var arr1 = [1, 2, 3]\nvar arr2 = arr1\nlet ptr1 = arr1.withUnsafeBufferPointer { $0.baseAddress }\nlet ptr2 = arr2.withUnsafeBufferPointer { $0.baseAddress }\nprint(ptr1 == ptr2)  // ?\n\narr2.append(4)\nlet ptr3 = arr2.withUnsafeBufferPointer { $0.baseAddress }\nprint(ptr1 == ptr3)  // ?
```


   **A.** true, true

✅ **B.** true, false

   **C.** false, false

   **D.** false, true


**정답**: B


💡 **힌트**: COW 동작 방식을 떠올려보세요. 복사 직후엔 같은 버퍼를 공유, append 시점에 새 버퍼 할당.


### 문제 2

Existential Container의 inline value buffer 크기는?


   **A.** 8 bytes (1 word)

   **B.** 16 bytes (2 words)

✅ **C.** 24 bytes (3 words)

   **D.** 32 bytes (4 words)


**정답**: C


💡 **힌트**: 64비트 시스템에서 word는 8바이트입니다. Existential은 3 words를 inline buffer로 사용합니다.


### 문제 3

struct가 힙에 저장될 수 있는 경우가 **아닌 것**은?


   **A.** 24바이트 초과 크기로 Existential Container에 담길 때

   **B.** 클로저에 의해 캡처될 때

✅ **C.** 원시 타입(Int, Double)을 프로퍼티로 가질 때

   **D.** 제네릭 컨텍스트에서 specialization이 실패했을 때


**정답**: C


💡 **힌트**: Int, Double 같은 작은 원시 타입을 프로퍼티로 갖는 것 자체는 힙 할당과 무관합니다.


