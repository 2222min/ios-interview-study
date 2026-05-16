# Day 2 — ARC / 메모리 관리

**태그**: ARC · HeapObject · Side Table · weak/unowned · Retain Cycle · Autorelease Pool

---

## 📝 핵심 정리


### 1. ARC 기본 — 자동 메모리 관리의 원리

_아이콘: `blue`_


### ARC가 무엇이고, Swift는 메모리를 어떻게 관리하나요?

**ARC = Automatic Reference Counting.** 컴파일 타임에 컴파일러가 코드를 분석해서 `retain`(참조 카운트 +1)과 `release`(참조 카운트 -1) 호출을 자동으로 삽입해주는 메모리 관리 시스템입니다.

핵심 원리: **"참조하는 곳이 몇 개인지 세고, 0이 되면 즉시 해제"**

```swift
// 우리가 작성한 코드:
func process() {
    let user = User(name: "철수")
    print(user.name)
}

// 컴파일러가 실제로 변환한 코드 (의사 코드):
func process() {
    let user = User(name: "철수")  // retain → count=1
    print(user.name)
    // release → count=0 → deinit 호출 → 메모리 해제
}
```

### ARC vs GC 비교

| 항목 | ARC | GC (Java, Go 등) |
|---|---|---|
| **동작 시점** | 컴파일 타임 코드 삽입 | 런타임 주기적 실행 |
| **해제 시점** | 참조 카운트 0 즉시 (결정적) | GC 사이클 도래 시 (비결정적) |
| **Pause** | 없음 | GC pause 발생 |
| **순환 참조** | 자동 해결 X (개발자 책임) | 자동 해결 O |

### ARC는 어떤 타입에 적용되나요?

**reference type(class, closure, actor)에만 적용됩니다.**

| 타입 | ARC? | 메모리 관리 |
|---|---|---|
| struct | ❌ | 스택 자동 해제 (스코프 끝) |
| enum | ❌ | 스택 자동 해제 |
| class | ✅ | 힙 + 참조 카운팅 |
| closure | ✅ | 힙 (closure context) |
| actor | ✅ | 힙 (참조 타입) |

### Strong Reference란?

"이 객체를 사라지지 않게 잡아두겠다"고 선언하는 참조입니다. `var/let`으로 선언하면 별도 키워드 없이 모두 strong reference입니다.

```swift
let a = User()    // strong (count: 1)
let b = a         // strong (count: 2)
let c = a         // strong (count: 3)
// a, b, c가 모두 스코프 벗어나야 deinit 호출됨
```

### Reference Count는 언제 증가/감소?

**증가:**

- 변수에 객체 할당 (`let x = obj`)

- 함수 파라미터로 전달 (대부분의 경우)

- 컬렉션에 추가

- 클로저가 캡처

- 다른 객체의 strong 프로퍼티에 할당

**감소:**

- 변수가 스코프를 벗어남

- nil 또는 다른 객체로 재할당

- 컬렉션에서 제거

- 클로저 해제

참고: `-O` 최적화 시 컴파일러가 불필요한 retain/release를 제거하여, 사람이 예상하는 횟수와 실제 호출 횟수가 다를 수 있습니다 (Guaranteed Parameter 컨벤션).

### Reference Count가 0이 되면?

- **deinit 호출** — 객체의 deinit 메서드 실행

- **자식 프로퍼티 release** — strong 프로퍼티들 RC -1 (연쇄 해제)

- **weak 참조 nil 처리** — 이 객체를 weak로 참조하던 변수들이 모두 nil

- **메모리 해제** — 힙 메모리를 시스템에 반환

- **Side Table 정리** — weak count도 0이면 Side Table 자체도 해제

### deinit이 호출되지 않으면 의심할 4가지

- **Retain Cycle**: 두 객체가 서로 strong 참조 → 영원히 RC가 0 안 됨

- **Closure Capture**: 클로저가 self를 strong 캡처한 채 어딘가에 저장됨

- **Timer / NotificationCenter**: Timer.target은 strong, observer 해제 누락

- **전역 변수 / 싱글톤 보관**: 의도치 않게 전역에 저장되어 영원히 살아있음

**탐지:** deinit에 print 추가 → 화면 dismiss 후 안 찍히면 의심. Memory Graph Debugger로 시각화. Instruments Leaks 자동 탐지.

> 💡 **💡 면접 답변 정석:** "ARC는 컴파일 타임에 retain/release를 자동 삽입하는 메모리 관리 시스템으로, class·closure·actor 같은 reference type에만 적용됩니다. struct/enum은 스택 기반 자동 해제. RC가 0이 되면 즉시 deinit 호출 후 메모리 해제 + weak 참조 nil 처리. deinit이 호출되지 않으면 retain cycle, closure capture, Timer/Notification 같은 잠재 누수를 의심합니다."


### 2. HeapObject — 클래스 인스턴스의 메모리 구조

_아이콘: `green`_


### Swift 클래스 인스턴스는 메모리 어디에?

**항상 힙(Heap)에 저장됩니다.** 스택에 저장되는 경우는 없습니다.

이유:

- lifetime이 함수 스코프와 무관하게 길어질 수 있음 (다른 변수에 할당, 컬렉션에 추가)

- ARC가 추적해야 하므로 고정된 주소가 필요. 스택은 frame이 사라지면 주소도 사라짐

- 크기가 동적이거나 큰 경우가 많아 스택에 부적합

### 클래스 인스턴스 내부에는 무엇이 들어있나?

"**헤더 + 프로퍼티**" 구조입니다.

```swift
┌─────────────────────────────────────┐
│ HEADER (16 bytes, 우리가 안 보임)    │
│  ├─ metadata 포인터 (8B)            │  ← 타입 정보 (isa)
│  └─ refCounts (8B)                  │  ← 참조 카운트
├─────────────────────────────────────┤
│ PROPERTIES (우리가 선언한 것)        │
│  ├─ age: Int (8B)                   │
│  ├─ name: String (16B)              │
│  └─ ...                             │
└─────────────────────────────────────┘
```

그래서 `class Empty { }`처럼 빈 클래스도 인스턴스 크기는 최소 16 bytes (헤더만).

### HeapObject는 무엇인가요?

**HeapObject는 Swift 런타임 내부에서 모든 클래스 인스턴스를 표현하는 C++ 구조체**입니다.

```swift
// Swift 런타임 소스 코드 (C++)
struct HeapObject {
    HeapMetadata const *metadata;  // 8B - 타입 정보 포인터
    InlineRefCounts refCounts;     // 8B - 참조 카운트 (비트 압축)
    // 그 다음에 프로퍼티들이 이어짐
};
```

모든 Swift class는 컴파일 시 이 HeapObject 구조를 헤더로 갖도록 변환됩니다. ObjC의 `isa` 포인터와 비슷하지만, refCount까지 인라인으로 포함시킨다는 점이 다릅니다.

### InlineRefCounts 비트 레이아웃

64bit(8 bytes) 안에 비트 단위로 여러 정보를 압축해 놓았습니다:

```swift
// InlineRefCounts (64bit)
//
// ┌──────────────┬───┬──────────────┬───┐
// │ strong count │ D │ unowned count│ U │
// │  (31 bits)   │   │  (31 bits)   │   │
// └──────────────┴───┴──────────────┴───┘
//
// strong: 일반 strong 참조 개수
// D (1bit): isDeinitializing — deinit 진행 중?
// unowned: unowned 참조 개수
// U (1bit): useSlowRC — Side Table 사용 중? (weak 있으면 1)
```

왜 비트로 압축했나? 모든 인스턴스에 8B만 추가하기 위해서. 인스턴스 100만 개면 8MB 차이.

### 실제 메모리 모습

```swift
class Person {
    var age: Int = 30
    var name: String = "철수"
}
let p = Person()

// 메모리 모습:
스택: [p (포인터 8B)] ──┐
                        │
힙:  ┌──────────────────▼─────────────────┐ ← 객체 시작 주소
     │ metadata (8B)                       │  헤더
     │ refCount (8B): strong=1, unowned=1  │  헤더
     ├─────────────────────────────────────┤
     │ age: 30 (8B)                        │  내 데이터
     │ name: "철수" (16B)                  │
     └─────────────────────────────────────┘
     총 ~40 bytes (+ malloc overhead)
```

### 값 타입은 항상 stack에 저장되나요?

**아닙니다.** 값 타입도 다음 경우엔 힙에 저장됩니다:

- **Existential Container의 24바이트 초과 struct**: 인라인 버퍼 초과 시 힙

- **클로저에 캡처된 변수**: closure context는 힙

- **Generic 컨텍스트 (specialization 실패 시)**: 컴파일러가 구체 타입 모르면 힙

- **Indirect enum case**: 재귀 enum은 힙

- **다른 class 인스턴스의 프로퍼티**: class가 힙에 있으니 같이 힙

그래서 정확한 표현은 "struct는 보통 인라인 저장(스택 또는 다른 객체의 일부)"이지 "항상 스택"은 아닙니다.

### let user = User()에서 user 변수와 인스턴스는 각각 어디?

| 대상 | 위치 | 설명 |
|---|---|---|
| `user` 변수 | 스택 (8B) | 힙 객체를 가리키는 포인터 |
| `User()` 인스턴스 | 힙 | 실제 객체 (헤더 16B + 프로퍼티) |

예외: 변수가 클로저에 캡처되면 user 변수도 힙(closure context). `self.user`처럼 프로퍼티면 self 객체 내부(역시 힙).

> 💡 **💡 면접 답변 정석:** "Swift 클래스 인스턴스는 항상 힙에 할당되며, Swift 런타임의 HeapObject 구조로 표현됩니다. 헤더에 metadata 포인터(8B)와 InlineRefCounts(8B)가 있고 그 뒤에 프로퍼티가 옵니다. 참조 카운트는 InlineRefCounts에 비트 단위로 압축되어 strong/unowned/플래그를 포함합니다. 변수 자체는 보통 스택의 포인터지만, 클로저 캡처되거나 다른 힙 객체에 속하면 힙에 위치합니다."


### 3. weak vs unowned — 약한 참조 완벽 정리

_아이콘: `purple`_


### 핵심 비교표

| 항목 | weak | unowned |
|---|---|---|
| Optional | 필수 | non-Optional 가능 |
| 대상 해제 후 | 자동 nil (zeroing) | 크래시 (dangling pointer) |
| Side Table | 필요 | 불필요 |
| 접근 비용 | ~10-20ns (간접 참조) | ~2-3ns (객체 내부 카운트) |
| 사용 시점 | 대상이 먼저 해제 가능 | 대상이 항상 더 오래 삶 |

### weak 동작

```swift
class Owner {
    weak var pet: Pet?    // weak는 항상 Optional!
}

let owner = Owner()
do {
    let pet = Pet()
    owner.pet = pet
    print(owner.pet?.name)  // "Pet 이름"
}  // 여기서 pet 해제
print(owner.pet)  // nil (자동으로 nil이 됨!)
```

### unowned 동작

```swift
class Pet {
    unowned let owner: Owner   // unowned는 non-Optional!
    init(owner: Owner) { self.owner = owner }
}

var owner: Owner? = Owner()
let pet = Pet(owner: owner!)
owner = nil  // owner 해제
print(pet.owner)  // 💥 크래시!
```

### weak는 왜 Optional이어야 하나요?

weak의 본질이 "대상이 해제되면 자동 nil"이기 때문입니다. nil이 될 수 있다 = Optional.

```swift
weak var d: SomeDelegate?   // ✅
weak let d: SomeDelegate?   // ❌ let은 변경 불가, 자동 nil 모순
weak var d: SomeDelegate    // ❌ Optional 아님
```

### unowned는 Optional이 될 수 있나요?

iOS 12+에서는 가능하지만 일반적이지 않습니다. unowned의 핵심 의도가 "절대 nil 안 됨"이라 Optional로 쓸 거면 weak가 자연스럽습니다.

### 실전 선택 가이드

| 상황 | 선택 | 이유 |
|---|---|---|
| delegate 패턴 | **weak** | delegate가 먼저 해제 가능 |
| closure에서 self 캡처 (비동기) | **weak** | 콜백 시점에 self 사라질 수 있음 |
| child → parent 참조 | **unowned** | parent가 항상 더 오래 삶 |
| 즉시 실행 closure에서 self | **unowned** | 실행 중엔 self 보장 |
| 확신 없을 때 | **weak** | 크래시보다 nil이 안전 |

### delegate를 weak로 선언하는 이유?

**retain cycle을 방지**하기 위해서입니다.

```swift
// 흔한 구조:
class VC: UIViewController, ServiceDelegate {
    let service = Service()       // VC → service (strong)
    
    override func viewDidLoad() {
        service.delegate = self   // service → delegate
    }
}

// delegate가 strong이면:
// VC → service → delegate(VC) → 순환 → VC.deinit 안 됨!

// delegate가 weak면:
// VC → service → delegate(weak, VC) → 순환 깨짐 → 정상 해제
```

### protocol에 AnyObject 제약이 필요한 이유?

**weak는 reference type(class)에만 적용 가능**하기 때문입니다.

```swift
protocol ServiceDelegate { ... }     // 제약 없음

class Service {
    weak var delegate: ServiceDelegate?
    // ❌ 컴파일 에러:
    // 'weak' must not be applied to non-class-bound 'ServiceDelegate'
}

// 해결: AnyObject 제약 추가
protocol ServiceDelegate: AnyObject { // class 전용으로 제한
    func didFinish()
}

class Service {
    weak var delegate: ServiceDelegate?  // ✅
}
```

AnyObject는 "이 프로토콜은 class만 채택할 수 있다"고 컴파일러에 알려줍니다. struct/enum은 채택 불가하므로 weak 안전.

### unowned(unsafe)는?

**절대 사용하지 마세요.** unowned 체크조차 하지 않아서 해제된 메모리에 그대로 접근합니다. 운 좋으면 동작하고, 운 나쁘면 알 수 없는 버그. C의 raw pointer와 같은 위험.

> 💡 **💡 면접 답변 정석:** "weak는 Optional이고 대상 해제 시 자동 nil(zeroing reference), unowned는 non-optional이고 해제 후 접근 시 크래시. weak는 Side Table을 통해 동작해서 약간의 성능 비용이 있고, unowned는 객체 내부 카운트만 사용해 빠릅니다. delegate는 weak로 retain cycle을 방지하며, 프로토콜에 AnyObject 제약을 추가해 class만 채택 가능하게 강제해야 weak 적용이 가능합니다. 의심스러우면 항상 weak가 안전합니다."


### 4. Side Table — weak가 동작하는 비밀

_아이콘: `orange`_


### 왜 객체 내부 refCount만으로는 weak를 관리할 수 없나요?

핵심 시나리오:

```swift
let p = Person()           // count: 1
weak var w1 = p
weak var w2 = p
weak var w3 = p
// p = nil 했을 때, w1, w2, w3를 어떻게 모두 nil로 만들지?
```

p가 해제될 때 "이 객체를 weak로 참조하는 모든 변수"를 찾아 nil 처리해야 합니다. 그러려면:

- weak 참조 목록을 어딘가에 저장해야 함

- 객체가 해제됐다는 신호를 weak 변수들에게 전달해야 함

- 객체 자체는 이미 해제되었지만 weak 변수들은 살아있어야 함

객체 내부에만 정보를 두면 객체 해제 시 그 정보도 사라집니다. 그래서 객체 외부에 별도 자료구조가 필요한데, 그게 **Side Table**입니다.

### Side Table이란?

weak 참조를 지원하기 위해 별도로 할당되는 추가 메모리 영역입니다.

```swift
// Swift 런타임 내부 (C++)
struct HeapObjectSideTableEntry {
    SideTableRefCounts refCounts;        // strong + unowned + weak count
    std::atomic<WeakRefCount> weakBits;  // weak 참조 개수
    HeapObject *object;                  // 원본 객체 포인터
};
```

### 일반 strong vs weak 메모리 모습

```swift
// 일반 strong: 직접 관리
HeapObject {
    metadata
    refCounts: strong=3  ← 단순 카운트만
    properties...
}

// weak가 있으면: Side Table을 거침
HeapObject {
    metadata
    refCounts: useSlowRC=1  ← "Side Table 보세요" 플래그
    properties...
}
       ↓ 별도 할당
SideTable {
    refCounts: strong=2, weak=3
    object: HeapObject 포인터
}
```

### weak 변수가 자동 nil 되는 원리

핵심 트릭: **weak 변수는 객체가 아니라 Side Table을 가리킨다.**

```swift
// 1. weak var w = p 시점:
//    Side Table 생성 (없으면)
//    Side Table.weakCount += 1
//    w는 Side Table을 가리킴 (객체를 직접 가리키지 않음!)
//
// 2. p 해제 시:
//    객체 strong count = 0 → deinit 호출
//    Side Table에 "객체 해제됨" 마킹
//    하지만 Side Table 자체는 아직 살아있음 (w가 참조 중)
//
// 3. w 접근 시:
//    Side Table에서 strong count 확인
//    strong == 0 → return nil
//
// 4. w도 해제되면:
//    Side Table.weakCount = 0
//    Side Table 자체도 해제
```

이 메커니즘 덕분에 객체가 사라져도 weak 변수는 안전하게 nil을 받을 수 있습니다.

### Side Table은 항상 생성되나요?

**아닙니다. Lazy하게 할당됩니다.**

```swift
let p = Person()
// 이 시점: Side Table 없음, HeapObject만 존재

weak var w = p
// 이 시점: Side Table 생성!
// HeapObject.refCounts.useSlowRC = 1로 설정
// 이후 모든 RC 작업이 Side Table을 통해 일어남
```

이래서 weak를 안 쓰는 객체는 Side Table 비용이 0입니다. weak를 쓰면 그때부터 추가 메모리(~32 bytes)가 발생.

### weak 참조가 많아지면 성능 영향은?

**(1) 메모리:**

- 객체당 Side Table: ~32 bytes

- weak 참조 1개당 추가: 8 bytes

- 객체 1만 개에 weak 5개씩이면 ~1.6MB

**(2) 접근 비용 비교 (실측 기준):**

| 참조 종류 | 접근 비용 | 설명 |
|---|---|---|
| strong | ~1ns | 직접 포인터 |
| unowned | ~2-3ns | 객체 내부 count 확인 |
| weak | ~10-20ns | Side Table 거쳐 atomic load |

### 최적화 패턴

```swift
// ❌ 매 반복마다 weak 접근 (Side Table 거침)
items.forEach {
    self?.process($0)        // 매번 ~15ns
}

// ✅ 한 번 strong 변환 후 사용
guard let strong = self else { return }
items.forEach {
    strong.process($0)        // 매번 ~1ns
}
```

UI 코드에선 무시할 수준이지만, hot loop에서는 차이가 누적됩니다.

> 💡 **💡 면접 답변 정석:** "weak 참조는 Side Table이라는 별도 자료구조를 통해 관리됩니다. 객체 내부 카운트만으로는 '객체 해제 후에도 살아있는 weak 변수에 nil 통보'가 불가능하기 때문이죠. weak 변수는 객체가 아닌 Side Table을 가리키고, 접근 시 strong count를 확인해 0이면 nil을 반환합니다. Side Table은 weak가 처음 생길 때 lazy하게 할당되며, 접근 비용이 strong보다 약간 높아 hot loop에서는 strong으로 변환 후 사용하는 게 유리합니다."


### 5. Retain Cycle — 실전 누수 패턴 진단

_아이콘: `blue`_


### Retain Cycle이란?

두 객체(또는 여러 객체)가 **서로를 strong으로 참조**하여 reference count가 영원히 0이 되지 않는 상황입니다.

```swift
// 가장 단순한 예
class A {
    var b: B?  // strong
}
class B {
    var a: A?  // strong
}

let a = A()
let b = B()
a.b = b
b.a = a
// 외부 변수 a, b가 사라져도:
// A의 retain count: 1 (B.a가 잡고 있음)
// B의 retain count: 1 (A.b가 잡고 있음)
// → 둘 다 영원히 해제 안 됨
```

### 왜 메모리 누수가 생기나요?

ARC가 객체를 해제하는 유일한 조건은 "strong count가 0". 순환 참조가 있으면 외부에서 더 이상 참조하지 않더라도 서로가 서로를 잡고 있어 count가 0이 안 됩니다.

- 아무도 사용하지 않는 객체가 메모리에 남음

- 같은 시나리오 반복 시 누수 누적 → 메모리 사용량 증가

- 최악의 경우 시스템이 앱을 메모리 부족으로 종료

**중요:** 단순 누수보다 **deinit이 호출되지 않는 것이 더 큰 문제**일 수 있습니다. deinit에서 정리하던 자원(파일, observer, Timer 등)이 영원히 정리 안 됨.

### 해결: 한쪽을 weak로

```swift
class A {
    var b: B?       // strong (A가 B를 소유)
}
class B {
    weak var a: A?  // ✅ weak로 변경
}

// 이제 a = nil 하면:
// 1. b.a는 weak이라 a retain count에 영향 없음
// 2. a count = 0 → A deinit 호출
// 3. A deinit 시 self.b 해제
// 4. b count = 0 → B deinit 호출
```

### 실전 패턴 1: Closure에서 self 캡처 (가장 흔함)

```swift
class ViewController: UIViewController {
    var dataLoader = DataLoader()
    
    override func viewDidLoad() {
        super.viewDidLoad()
        
        // ❌ 순환 참조!
        dataLoader.onComplete = { result in
            self.handleResult(result)  // closure가 self를 strong 캡처
        }
        // self → dataLoader → onComplete → self ... 순환!
        
        // ✅ 해결: [weak self]
        dataLoader.onComplete = { [weak self] result in
            guard let self = self else { return }
            self.handleResult(result)
        }
    }
}
```

### 실전 패턴 2: Delegate strong 참조

```swift
// ❌ delegate를 strong으로 (흔한 실수)
protocol DownloadDelegate {       // AnyObject 없음
    func didFinish()
}
class Downloader {
    var delegate: DownloadDelegate?  // 기본 strong!
}

class VC: UIViewController, DownloadDelegate {
    let downloader = Downloader()
    
    override func viewDidLoad() {
        downloader.delegate = self
        // VC → downloader → delegate(VC) → 순환!
    }
}

// ✅ 해결: AnyObject + weak
protocol DownloadDelegate: AnyObject {  // class 전용
    func didFinish()
}
class Downloader {
    weak var delegate: DownloadDelegate?  // weak!
}
```

### 실전 패턴 3: Timer (정말 흔한 함정)

```swift
class TimerVC: UIViewController {
    var timer: Timer?
    
    override func viewDidLoad() {
        super.viewDidLoad()
        
        // ❌ Timer는 target을 strong retain!
        timer = Timer.scheduledTimer(
            timeInterval: 1.0,
            target: self,           // ← strong!
            selector: #selector(tick),
            userInfo: nil,
            repeats: true
        )
        // RunLoop → Timer → self → timer → Timer ... 순환
        // 이 VC를 pop해도 절대 deinit 안 됨!
    }
    
    @objc func tick() { print("tick") }
}

// ✅ 해결 1: 명시적으로 invalidate
override func viewWillDisappear(_ animated: Bool) {
    super.viewWillDisappear(animated)
    timer?.invalidate()
    timer = nil
}

// ✅ 해결 2: Block-based Timer (iOS 10+)
timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
    self?.tick()
}
```

### 실전 패턴 4: NotificationCenter

```swift
// ❌ observer를 등록하고 해제 안 함
class VC: UIViewController {
    override func viewDidLoad() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleNotification),
            name: .someEvent,
            object: nil
        )
        // NotificationCenter가 self를 strong 보유
    }
}

// ✅ iOS 9+에서는 자동 해제되지만, 명시적 해제 권장
deinit {
    NotificationCenter.default.removeObserver(self)
}

// ✅ 또는 block 기반 + token 관리
let token = NotificationCenter.default.addObserver(
    forName: .someEvent, object: nil, queue: .main
) { [weak self] _ in
    self?.handle()
}
```

### 탐지 체크리스트

- 모든 클래스 deinit에 print 추가 → 화면 dismiss 후 안 찍히면 의심

- Memory Graph Debugger → 보라색 ! 표시 확인

- Instruments Leaks 정기 실행

- 코드 리뷰 시 closure에 [weak self] 누락 확인

- delegate 프로퍼티가 weak인지 확인

- Timer/NotificationCenter observer 해제 코드 확인

- 화면 진입을 10번 반복했을 때 객체가 10개 살아있으면 누수

> 💡 **💡 면접 답변 정석:** "Retain Cycle은 두 객체가 서로를 strong으로 참조하여 RC가 0이 되지 않는 상황입니다. 결과적으로 deinit이 호출되지 않아 메모리 누수와 자원 누수가 발생합니다. 가장 흔한 4가지 패턴은 closure capture, delegate strong 참조, Timer target retain, NotificationCenter observer 미해제입니다. 각각 [weak self], weak delegate + AnyObject 제약, invalidate 호출 또는 block-based Timer, removeObserver로 해결합니다. 저는 deinit에 print를 두고 Memory Graph Debugger로 정기 검증합니다."


### 6. Autorelease Pool — 대량 객체 메모리 제어

_아이콘: `green`_


### Autorelease Pool이 뭔가요?

Objective-C 시절부터 내려온 메모리 관리 메커니즘입니다. 풀에 담긴 객체들이 풀이 닫히는 시점에 한꺼번에 해제됩니다.

### 왜 필요한가요?

임시 객체가 많이 생성되는 루프에서 메모리 사용량이 폭발하는 걸 막기 위해서입니다.

```swift
// ❌ 메모리 폭발 예시
func processImages() {
    for i in 0..<1_000_000 {
        let str = NSString(format: "image_%d.png", i)
        // NSString은 autorelease 객체 → 풀 닫힐 때까지 살아있음
        // 함수 끝날 때까지 100만 개의 NSString이 메모리에 누적!
    }
}

// ✅ 매 반복마다 풀을 만들고 닫음
func processImages() {
    for i in 0..<1_000_000 {
        autoreleasepool {
            let str = NSString(format: "image_%d.png", i)
        }  // 여기서 풀 닫힘 → str 해제됨
    }
}
```

### 중요: 순수 Swift 객체는 대상이 아님

Swift native class와 struct는 autorelease pool과 무관합니다. ARC가 즉시 release하기 때문이죠. autoreleasepool이 영향을 미치는 건:

- NSString, NSArray, NSDictionary 등 NS- 접두사 객체

- Objective-C 라이브러리에서 가져온 객체

- 일부 Foundation API가 내부적으로 만드는 임시 객체

### 실무 사례 1: Core Data Batch Import

```swift
func importLargeDataset(_ records: [JSONRecord]) {
    let context = persistentContainer.newBackgroundContext()
    
    context.perform {
        // 100만 건을 1000건씩 나눠서 처리
        for chunk in records.chunked(into: 1000) {
            autoreleasepool {
                for record in chunk {
                    let entity = MyEntity(context: context)
                    entity.configure(with: record)
                }
                try? context.save()
                context.reset()  // managed objects 해제
            }
        }
    }
}
```

### 실무 사례 2: 이미지 처리

```swift
// 대량 이미지를 썸네일로 변환
func generateThumbnails(_ urls: [URL]) {
    for url in urls {
        autoreleasepool {
            guard let image = UIImage(contentsOfFile: url.path) else { return }
            let thumbnail = image.resized(to: CGSize(width: 100, height: 100))
            saveThumbnail(thumbnail, for: url)
            // image와 thumbnail이 풀 닫힐 때 해제됨
        }
    }
}
```

### main runloop에는 자동으로 있어요

iOS 앱의 main thread RunLoop은 매 사이클마다 autorelease pool을 자동으로 만들고 닫습니다. 그래서 일반적인 UI 코드에서는 명시적으로 쓸 필요가 없습니다.

> 💡 **💡 면접 포인트:** "Swift 자체는 ARC로 즉시 해제하지만, NSObject 브릿징 객체나 Core Data, ImageIO 같은 API들은 내부적으로 autorelease 객체를 사용합니다. 대량 데이터를 루프로 처리할 때 메모리 피크를 제어하려면 autoreleasepool을 명시적으로 써야 합니다. 저는 Core Data batch import에서 1000건마다 pool을 닫는 패턴으로 메모리 사용량을 1.2GB에서 200MB로 줄인 경험이 있습니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. ARC와 GC의 가장 큰 차이는? `[기본 / 빈출]`

**해제 시점의 결정성**입니다.

ARC: 컴파일 타임 코드 삽입 → 참조 카운트 0 즉시 deinit (deterministic, 코드만 보면 정확히 예측 가능).

GC: 런타임 주기적 수집 → 언제 해제될지 정확히 알 수 없음.

이 차이로 인해:
• ARC: GC pause 없음 → UI 반응성 우수, 모바일 적합
• ARC: 파일 핸들, 락 해제 같은 RAII 패턴 가능
• GC: 순환 참조 자동 해결 → 개발자 부담 적음
• GC: 메모리 사용량이 일시적으로 더 높을 수 있음


### Q2. ARC가 적용되는 타입은? struct, enum, class 중 어디? `[기본 / 빈출]`

**class, closure, actor 같은 reference type에만 적용됩니다.**

struct, enum 같은 value type은 ARC 대상이 아닙니다. 스택에 저장되어 스코프 종료 시 자동 해제되거나, 다른 객체에 포함되어 그 객체와 함께 관리됩니다.

주의: struct 안에 class 프로퍼티가 있다면 그 class 프로퍼티는 ARC 적용. struct 자체는 아닙니다.


### Q3. Strong Reference가 정확히 무엇인가요? `[기본 / 빈출]`

\"이 객체를 사라지지 않게 잡아두겠다\"고 선언하는 참조입니다. **strong reference가 +1되면 retain count가 +1**되어 객체가 살아있게 됩니다.

Swift에서는 별도 키워드 없이 `var/let`으로 선언하면 모두 strong입니다 (ObjC의 `__strong`이 기본값이 된 셈).

대비되는 개념: weak(자동 nil), unowned(non-owning).

Strong이 의미 있는 이유: ARC가 \"누군가가 잡고 있는가?\"를 판단하는 기준이 strong count이기 때문.


### Q4. Reference Count는 언제 증가하고 언제 감소하나요? `[기본 / 빈출]`

**증가:**
• 변수에 할당 (`let x = obj`)
• 함수 파라미터로 전달 (대부분의 경우)
• 컬렉션(Array, Dictionary)에 추가
• 클로저가 캡처
• 다른 객체의 strong 프로퍼티에 할당

**감소:**
• 변수가 스코프를 벗어남
• 변수에 nil/다른 객체 할당
• 컬렉션에서 제거
• 클로저 해제

주의: 컴파일러가 -O 최적화에서 불필요한 retain/release를 제거할 수 있어 사람이 예상하는 횟수와 실제 호출 횟수가 다를 수 있습니다 (Guaranteed Parameter 컨벤션).


### Q5. Reference Count가 0이 되면 어떤 일이 발생하나요? `[기본 / 빈출]`

순서대로:

1. **deinit 호출**: 객체의 deinit 메서드 실행
2. **자식 프로퍼티 release**: strong 참조들의 RC가 -1 (연쇄 해제)
3. **weak 참조 nil 처리**: 이 객체를 weak로 참조하던 변수들이 모두 nil이 됨
4. **메모리 해제**: 힙 메모리를 시스템에 반환
5. **Side Table 정리**: weak count도 0이면 Side Table 자체도 해제

이 순서는 결정적(deterministic)이라 시점이 정확히 예측 가능합니다.


### Q6. deinit이 호출되지 않으면 어떤 상황을 의심하나요? `[기본 / 빈출]`

가장 흔한 4가지 원인:

1. **Retain Cycle**: 두 객체가 서로 strong 참조 → 영원히 RC가 0 안 됨
2. **Closure Capture**: 클로저가 self를 strong 캡처한 채 어딘가에 저장됨
3. **Timer / NotificationCenter**: Timer의 target은 strong, observer 해제 누락
4. **전역 변수 / 싱글톤 보관**: 의도치 않게 전역에 저장되어 영원히 살아있음

탐지: deinit에 print 추가 → 화면 dismiss 후 안 찍히면 의심. Memory Graph Debugger로 시각화. Instruments Leaks 자동 탐지.


### Q7. closure capture list의 동작 원리는? `[심화 / 빈출]`

capture list는 **클로저가 생성되는 시점에 변수를 캡처하는 방식을 명시**하는 문법입니다.

기본 동작:
• reference type: strong 캡처 (retain count +1)
• value type: 값 복사

capture list로 변경 가능:
• `[weak self]`: weak 캡처
• `[unowned self]`: unowned 캡처
• `[x = someValue]`: 클로저 생성 시점의 값으로 복사
• `[weak delegate, x = currentX]`: 여러 개 동시 가능

예시:
```swift
var x = 10\nlet closure = { [x] in print(x) }  // 10 캡처\nx = 20\nclosure()  // 10 출력 (x=20이 아님!)
```


### Q8. weak self 후 guard let self 하면 retain count가 올라가나요? `[기본 / 빈출]`

맞습니다. **guard let self 시점에 strong count가 +1됩니다.** 클로저 안에서 strong 참조가 임시로 만들어지는 거죠.

중요한 건 **'클로저 스코프가 끝나면 즉시 release 된다'**는 점입니다. 그러니 deinit이 '지연'되는 것이지 '방지'되는 것은 아닙니다.

주의: 만약 클로저 안에서 또 다른 async 작업을 시작하고 거기서도 self를 캡처하면, 그 동안은 self가 살아있게 됩니다. 의도치 않은 lifetime 연장이 될 수 있어요.


### Q9. Combine에서 순환 참조를 어떻게 방지하나요? `[기본 / 빈출]`

두 가지 방법:

**1. AnyCancellable + Set**
모든 subscription을 `Set<AnyCancellable>`에 저장합니다. 소유자가 deinit될 때 Set이 해제되고, 그 안의 AnyCancellable들이 해제되면서 자동으로 cancel됩니다.

**2. sink 클로저에서 [weak self]**
일반 closure와 똑같이 [weak self]로 캡처합니다.

**주의:** `.assign(to: \\.title, on: self)`는 self를 strong 캡처합니다! 대신 `.assign(to: &$title)`(@Published 프로퍼티에 직접)을 쓰는 게 안전합니다.


### Q10. Swift 클래스 인스턴스는 메모리 어디에 저장되나요? `[기본 / 빈출]`

**항상 힙(Heap)에 저장됩니다.** 스택에 저장되는 경우는 없습니다.

이유:
1. lifetime이 함수 스코프와 무관하게 길어질 수 있음 (다른 변수에 할당, 컬렉션에 추가 등)
2. ARC가 추적해야 하므로 고정된 주소가 필요한데, 스택은 frame이 사라지면 주소도 사라짐
3. 크기가 동적이거나 큰 경우가 많아 스택에 부적합

변수 자체(`let user = ...`의 user)는 보통 스택의 포인터지만, 실제 객체는 힙입니다.


### Q11. 클래스 인스턴스 내부에는 어떤 정보들이 들어있나요? `[심화 / 빈출]`

\"헤더 + 프로퍼티\" 구조입니다.

**HEADER (16 bytes, 우리가 안 보이는 부분):**
• metadata 포인터 (8B): 타입 정보, vtable, ObjC isa 역할
• InlineRefCounts (8B): strong/unowned count + 플래그

**PROPERTIES:**
• 우리가 선언한 프로퍼티들이 순서대로 저장
• 프로퍼티 정렬 규칙(alignment) 적용

그래서 `class Empty { }`처럼 빈 클래스도 인스턴스 크기는 최소 16 bytes입니다.


### Q12. HeapObject 개념을 들어본 적 있나요? `[심화]`

**HeapObject는 Swift 런타임 내부에서 모든 클래스 인스턴스를 표현하는 C++ 구조체**입니다.

```swift
struct HeapObject {\n    HeapMetadata const *metadata;  // 8B\n    InlineRefCounts refCounts;     // 8B\n    // 그 다음에 프로퍼티들\n};
```
모든 Swift class는 컴파일 시 이 HeapObject 구조를 헤더로 갖도록 변환됩니다.

ObjC와 비교: ObjC도 isa 포인터가 있지만, refCount는 별도 테이블로 관리. Swift는 refCount까지 인라인으로 객체에 포함시켜 메모리 효율이 좋습니다.


### Q13. InlineRefCounts에는 어떤 정보가 압축되어 있나요? `[심화]`

64bit(8 bytes) 안에 비트 단위로 다음 정보가 압축되어 있습니다:

• **strong count (31 bits)**: 일반 strong 참조 개수
• **isDeinitializing (1 bit)**: deinit 진행 중 플래그
• **unowned count (31 bits)**: unowned 참조 개수
• **useSlowRC (1 bit)**: Side Table 사용 여부 (weak 있으면 1)

왜 압축했나? 모든 인스턴스에 8B 추가만 하기 위해서. 인스턴스가 100만 개면 8MB 차이입니다.

weak 참조가 추가되면 useSlowRC가 1로 변경되고, 모든 RC 작업이 Side Table을 통해 일어납니다.


### Q14. 값 타입은 항상 stack에 저장되나요? `[심화 / 빈출]`

**아닙니다.** 값 타입도 다음 경우엔 힙에 저장됩니다:

1. **Existential Container의 24바이트 초과 struct**: 인라인 버퍼 초과 시 힙 할당
2. **클로저에 캡처된 변수**: closure context는 힙
3. **Generic 컨텍스트 (specialization 실패 시)**: 컴파일러가 구체 타입 모르면 힙
4. **Indirect enum case**: 재귀 enum은 힙
5. **다른 class 인스턴스의 프로퍼티**: class가 힙에 있으니 같이 힙

그래서 정확한 표현은 \"struct는 보통 인라인 저장(스택 또는 다른 객체의 일부)\"입니다.


### Q15. let user = User()에서 user 변수와 인스턴스는 각각 어디에? `[기본 / 빈출]`

**일반적인 경우:**
• `user` 변수 → 스택 (8B 포인터)
• `User()` 인스턴스 → 힙 (헤더 16B + 프로퍼티)

**예외:**
• 변수가 클로저에 캡처되면 user 변수도 힙(closure context)으로 이동
• `self.user`처럼 프로퍼티라면 self 객체 안에 포함되어 힙
• 변수가 컬렉션에 들어가면 컬렉션 버퍼(보통 힙)에 위치

중요: 변수는 \"객체를 가리키는 포인터\"이고 객체 자체와 다릅니다. 변수의 위치와 객체의 위치는 별개입니다.


### Q16. weak는 왜 항상 Optional이어야 하나요? `[기본 / 빈출]`

weak의 본질이 **\"대상이 해제되면 자동으로 nil이 된다\"**이기 때문입니다. nil이 될 수 있다는 것 자체가 Optional이라는 뜻이죠.

```swift
weak var d: SomeDelegate?  // ✅\nweak let d: SomeDelegate?  // ❌ let은 변경 불가, 자동 nil 처리 모순\nweak var d: SomeDelegate   // ❌ Optional 아님
```
let도 안 됩니다 — 자동으로 nil이 되는데 let이면 모순이거든요.

비교: unowned는 \"절대 nil 안 된다\"는 강한 의도라서 non-Optional이 자연스럽습니다.


### Q17. unowned는 Optional이 될 수 없나요? `[심화]`

iOS 12+에서는 **가능하지만 일반적이지 않습니다**.

```swift
// 일반적: non-optional\nunowned let owner: Owner\n\n// 가능하지만 드물게 사용\nunowned(safe) var ref: SomeClass?
```
unowned의 핵심 의도는 \"대상이 절대 nil이 되지 않는다고 확신\"하는 것입니다. Optional로 쓸 거면 이미 nil이 될 수 있다는 뜻이라 weak를 쓰는 게 더 자연스럽습니다.

역사적 배경: 옛 Swift에서는 unowned는 항상 non-optional이었습니다. 이후 더 유연한 사용을 위해 Optional도 허용되었지만, 의미적으로 weak가 더 적합한 경우가 대부분입니다.


### Q18. weak 참조 대상이 해제되면 weak 변수에는? `[기본 / 빈출]`

자동으로 **nil**이 됩니다. 이를 \"zeroing reference\"라고 부릅니다.

```swift
weak var w: Pet?\ndo {\n    let p = Pet()\n    w = p\n    print(w != nil)  // true\n}  // p 해제\nprint(w != nil)  // false (자동 nil)
```
이게 가능한 원리: 객체가 해제될 때 Side Table을 통해 모든 weak 참조를 추적하고 nil 처리. 그래서 weak를 사용하려면 객체가 Side Table을 가질 수 있어야 하고, 이는 자동으로 처리됩니다.


### Q19. unowned 대상이 먼저 해제되면 어떤 문제가? `[기본 / 빈출]`

접근하는 순간 **크래시**가 발생합니다. EXC_BAD_ACCESS 또는 fatalError.

```swift
var owner: Owner? = Owner()\nlet pet = Pet(owner: owner!)\nowner = nil  // owner 해제\n\nprint(pet.owner)  // 💥 크래시!
```
unowned는 \"이 참조가 항상 유효하다\"고 컴파일러에 약속하는 것입니다. 그 약속을 어기면 dangling pointer 접근이 되어 즉시 크래시.

그래서 unowned는 **대상이 자기보다 항상 오래 산다는 확신**이 있을 때만 써야 합니다. 의심스러우면 weak가 안전합니다.


### Q20. unowned는 언제 쓰는 게 안전한가요? `[심화 / 빈출]`

**대상 객체의 lifetime이 자신보다 항상 길거나 같다고 확신할 수 있을 때**만 안전합니다.

대표적인 안전한 케이스:
• Parent-child 관계에서 child가 parent를 참조 (parent가 항상 더 오래 삶)
• 즉시 실행되는 closure에서 self 캡처
• ViewModel이 자신을 소유하는 ViewController를 참조 (생명주기가 동기화됨)

위험한 케이스:
• 비동기 콜백 (네트워크, 타이머) — 콜백 시점에 객체가 사라졌을 수 있음
• delegate 패턴 — delegate가 먼저 dealloc될 가능성

확신이 없으면 weak가 정답입니다.


### Q21. delegate 패턴에서 delegate를 weak로 선언하는 이유는? `[기본 / 빈출]`

**retain cycle을 방지**하기 위해서입니다.

delegate 패턴의 일반 구조:
• ViewController가 Service를 strong 보유
• Service가 delegate(=ViewController)를 보유

만약 delegate가 strong이면:
VC → Service (strong) → delegate=VC (strong) → 순환!

delegate를 weak로 선언하면 순환이 끊어져 VC가 정상 해제됩니다.

이 패턴은 Apple의 UIKit 전체에서 일관되게 적용됩니다 (UITableView.delegate, UIScrollView.delegate 등 모두 weak).


### Q22. protocol에 AnyObject 제약이 필요한 이유는? `[기본 / 빈출]`

**weak가 reference type(class)에만 적용 가능하기 때문**입니다.

struct/enum 같은 value type은 weak로 만들 수 없습니다 (값 자체가 복사되니까 \"참조가 없어졌다\"는 개념이 없음).

```swift
protocol ServiceDelegate { ... }  // class 제약 없음\n\nclass Service {\n    weak var delegate: ServiceDelegate?\n    // ❌ 컴파일 에러:\n    // 'weak' must not be applied to non-class-bound 'ServiceDelegate'\n}\n\n// 해결:\nprotocol ServiceDelegate: AnyObject {  // class 전용\n    func didFinish()\n}\n\nclass Service {\n    weak var delegate: ServiceDelegate?  // ✅\n}
```
AnyObject는 \"이 프로토콜은 class만 채택할 수 있다\"고 컴파일러에 알려주는 제약입니다.


### Q23. Side Table이 무엇인가요? `[심화 / 빈출]`

**weak 참조를 지원하기 위해 별도로 할당되는 추가 메모리 영역**입니다.

```swift
struct HeapObjectSideTableEntry {\n    SideTableRefCounts refCounts;\n    atomic<WeakRefCount> weakBits;\n    HeapObject *object;  // 원본 객체 포인터\n};
```
특징:
• 객체별로 하나씩 만들어짐 (lazy 할당)
• 처음에는 없다가 weak 참조가 처음 생길 때 할당
• 메모리: 약 32 bytes
• thread-safe (atomic 연산 사용)

왜 \"Side\"? HeapObject가 메인이고, 이건 보조(side) 역할이라는 의미입니다.


### Q24. 객체 해제 시 weak 변수가 자동 nil 되는 원리는? `[심화 / 빈출]`

실제 동작 순서:

1. **weak var w = p 시점**
• Side Table 생성 (없으면)
• Side Table.weakCount += 1
• w는 Side Table을 가리킴 (객체를 직접 가리키지 않음!)

2. **p 해제 시**
• 객체 strong count = 0 → deinit 호출
• Side Table에 \"객체 해제됨\" 마킹
• 하지만 Side Table 자체는 아직 살아있음 (w가 참조 중)

3. **w 접근 시**
• Side Table에서 strong count 확인
• strong == 0 → return nil

4. **w도 해제되면**
• Side Table.weakCount = 0
• Side Table 자체도 해제

이 메커니즘 덕분에 객체가 사라져도 weak 변수는 안전하게 nil을 받을 수 있습니다.


### Q25. Side Table은 항상 생성되나요? `[심화]`

**아닙니다. Lazy하게 할당됩니다.**

처음에는 없다가, **weak 참조가 처음 생기는 시점**에 할당됩니다.

```swift
let p = Person()\n// 이 시점: Side Table 없음, HeapObject만 존재\n\nweak var w = p\n// 이 시점: Side Table 생성!\n// HeapObject.refCounts.useSlowRC = 1로 설정\n// 이후 모든 RC 작업이 Side Table 통해 일어남
```
이래서 weak를 안 쓰는 객체는 Side Table 비용이 0입니다. weak를 쓰면 그때부터 추가 메모리(~32 bytes)가 발생.

이 lazy 전략 덕분에 ARC 오버헤드가 최소화됩니다.


### Q26. weak 참조가 많아지면 성능 영향은? `[심화]`

두 가지 영향:

**(1) 메모리:**
• 객체당 Side Table: ~32 bytes
• weak 참조 1개당: 추가 8 bytes
• 객체 1만 개에 weak 5개씩이면 ~1.6MB

**(2) 접근 비용:**
• strong: ~1ns (직접 포인터)
• unowned: ~2-3ns (객체 내부 count 확인)
• weak: ~10-20ns (Side Table 거쳐 atomic load)

UI 코드에선 무시할 수준이지만, hot loop에서는 차이가 누적됩니다.

최적화 패턴:
```swift
// ❌ 매 반복마다 weak 접근\nitems.forEach { self?.process($0) }  // 매번 ~15ns\n\n// ✅ 한 번 strong 변환 후 사용\nguard let strong = self else { return }\nitems.forEach { strong.process($0) }  // 매번 ~1ns
```


### Q27. Retain Cycle이 발생하면 왜 메모리 누수가 생기나요? `[기본 / 빈출]`

ARC가 객체를 해제하는 유일한 조건은 **\"strong count가 0\"**입니다.

순환 참조가 있으면 외부에서 더 이상 참조하지 않더라도 서로가 서로를 잡고 있어 count가 0이 안 됩니다. 결과:

1. **아무도 사용하지 않는 객체가 메모리에 남음** (메모리 누수)
2. 같은 시나리오를 반복하면 누수가 누적되어 메모리 사용량 증가
3. 최악의 경우 시스템이 앱을 메모리 부족으로 종료

중요: 단순 메모리 누수보다 **deinit이 호출되지 않는 것이 더 큰 문제**일 수 있습니다. deinit에서 정리하던 자원(파일, observer, Timer 등)이 영원히 정리 안 되니까요.


### Q28. 다음 closure 코드의 retain cycle 문제는? `[기본 / 빈출]`

흔한 closure capture 문제:
```swift
class VC: UIViewController {\n    var loader = DataLoader()\n    override func viewDidLoad() {\n        loader.onComplete = { result in\n            self.handleResult(result)  // ⚠️\n        }\n    }\n}
```
**분석:**
• VC → loader (strong, 프로퍼티)
• loader → onComplete (strong, 프로퍼티)
• onComplete → self (strong, 캡처)
• self == VC → 순환 완성!

**증상:** VC를 dismiss해도 deinit이 호출되지 않음. 화면 진입을 반복하면 메모리에 VC 인스턴스가 누적.

**해결:**
```swift
loader.onComplete = { [weak self] result in\n    guard let self = self else { return }\n    self.handleResult(result)\n}
```


### Q29. Timer가 메모리 누수를 일으키는 이유와 해결법은? `[기본 / 빈출]`

**Timer.scheduledTimer(target:)**의 target 파라미터는 strong reference입니다.

발생 구조:
• RunLoop → Timer (strong, 등록)
• Timer → target=self (strong)
• VC → timer (strong, 프로퍼티)
• 순환! VC를 pop해도 Timer가 살아서 self를 잡고 있음

**해결 1: 명시적 invalidate**
```swift
override func viewWillDisappear(_ animated: Bool) {\n    super.viewWillDisappear(animated)\n    timer?.invalidate()\n    timer = nil\n}
```
**해결 2: Block-based Timer (iOS 10+) + weak self**
```swift
timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in\n    self?.tick()\n}
```
참고: invalidate는 RunLoop에서 Timer를 제거하므로 순환의 핵심 고리를 끊습니다.


---


## ✏️ 퀴즈


### 문제 1

다음 중 ARC에 대한 설명으로 **올바르지 않은 것**은?


   **A.** 컴파일 타임에 retain/release 코드를 자동 삽입한다

✅ **B.** 순환 참조를 자동으로 탐지하고 해제한다

   **C.** strong reference count가 0이 되면 즉시 deinit이 호출된다

   **D.** atomic operation으로 thread-safe하게 카운트를 관리한다


**정답**: B


💡 **힌트**: ARC는 순환 참조를 자동으로 해결하지 못합니다. 그래서 weak/unowned를 사용해 개발자가 명시적으로 해결해야 합니다.


### 문제 2

weak reference에 대한 설명으로 **올바른 것**은?


   **A.** HeapObject 내부에 직접 weak count가 저장된다

   **B.** Side Table 없이도 동작 가능하다

✅ **C.** 참조 대상이 해제되면 자동으로 nil이 된다 (zeroing)

   **D.** unowned보다 접근 비용이 낮다


**정답**: C


💡 **힌트**: weak는 'zeroing reference'라고도 불립니다. 대상이 해제되면 자동으로 nil이 되며, 이를 위해 Side Table이 필요합니다.


### 문제 3

다음 코드에서 메모리 누수가 발생하는 이유는?

```swift
class VC: UIViewController {\n  var timer: Timer?\n  override func viewDidLoad() {\n    super.viewDidLoad()\n    timer = Timer.scheduledTimer(\n      timeInterval: 1, target: self,\n      selector: #selector(tick),\n      userInfo: nil, repeats: true)\n  }\n}
```


✅ **A.** Timer가 target 파라미터(self)를 strong으로 retain하기 때문

   **B.** viewDidLoad에서 Timer를 생성하면 안 되기 때문

   **C.** #selector 방식은 항상 메모리 누수를 유발하기 때문

   **D.** Timer는 반드시 main thread에서만 사용해야 하기 때문


**정답**: A


💡 **힌트**: Timer(target:)에서 target은 strong reference입니다. RunLoop → Timer → self → timer → Timer 순환이 발생합니다. invalidate를 호출하거나 block-based Timer를 사용해야 합니다.


### 문제 4

`[weak self]`를 사용할 때 다음 중 가장 권장되는 패턴은?


   **A.** self?.method() 처럼 매번 옵셔널 체이닝을 사용한다

✅ **B.** guard let self = self else { return } 으로 strong 변환 후 사용한다

   **C.** [unowned self]로 변경하여 항상 빠르게 동작하도록 한다

   **D.** capture list 없이 self를 그대로 사용한다


**정답**: B


💡 **힌트**: 매번 self?.를 쓰면 매번 Side Table을 통한 weak 접근이 발생합니다. guard let으로 한 번 strong 변환하면 그 이후로는 빠른 직접 접근이 가능합니다.


