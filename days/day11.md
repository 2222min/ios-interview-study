# Day 11 — SwiftUI 렌더링 엔진과 상태 관리

**태그**: SwiftUI · Attribute Graph · @State · @StateObject · Body 재호출

---

## 📝 핵심 정리


### 1. SwiftUI View는 struct다 (가장 중요한 개념)

_아이콘: `blue`_


### UIKit과 SwiftUI의 근본적 차이

UIKit의 UIView는 class입니다. 한 번 만들면 계속 살아있고, frame이나 alpha를 직접 변경합니다.

SwiftUI의 View는 **struct**입니다. 그리고 매번 새로 생성됩니다.

```swift
// UIKit 사고방식:
let view = UIView()
view.backgroundColor = .red    // 직접 변경
view.alpha = 0.5               // 직접 변경
// view 인스턴스는 계속 같은 객체

// SwiftUI 사고방식:
struct MyView: View {
    @State var color = Color.red
    var body: some View {
        Rectangle()
            .fill(color)
            .opacity(0.5)
    }
}
// MyView는 "어떻게 그릴지에 대한 설명서"
// body가 호출될 때마다 새 struct가 만들어짐!
```

### 그럼 매번 다 새로 그리는 건가요? 비효율적이지 않나요?

아닙니다. SwiftUI는 새 View struct를 만들고, **이전 트리와 비교(diff)하여 변경된 부분만** 실제 UI에 반영합니다. React와 비슷한 컨셉이에요.

```swift
struct CounterView: View {
    @State private var count = 0
    
    var body: some View {
        // count 변경 시 body 다시 호출됨
        VStack {
            Text("카운트: \\(count)")  // count 의존
            Button("증가") {
                count += 1
            }
        }
    }
}

// count가 0 → 1 변경 시:
// 1. body 다시 호출
// 2. 새 VStack { Text("카운트: 1"), Button("증가") } 생성
// 3. SwiftUI가 이전 트리와 비교
// 4. Text의 내용만 바뀐 걸 발견
// 5. Text의 텍스트만 업데이트 (Button은 그대로 둠)
```

### View Identity

SwiftUI가 "이 View가 같은 View인가, 새로운 View인가"를 판단하는 기준입니다.

- **Structural Identity**: 위치(코드 트리에서의 자리) 기반

- **Explicit Identity**: `.id()`로 명시

```swift
// id가 같으면 → 같은 View로 간주, 상태 유지, 부드러운 전환
// id가 다르면 → 다른 View, 상태 리셋, 새로 생성

ForEach(items, id: \\.self) { item in
    Text(item.title)
}
// id 변경되면 Text가 새로 생성됨 (애니메이션 시작 가능)
```

> 💡 **💡 면접 포인트:** "SwiftUI는 'View = 함수 (State → UI)'라는 함수형 사고방식입니다. body는 자주 호출되지만 실제 UI 변경은 diff 결과에 따라 최소한만 일어납니다. 이 모델 덕분에 상태 관리가 단순해지죠. 단, 대량 List에서 불필요한 body 재호출이 일어나면 성능이 떨어지므로 View를 작은 단위로 분리해야 합니다."


### 2. Attribute Graph (SwiftUI의 비밀)

_아이콘: `green`_


### Attribute Graph가 뭔가요?

SwiftUI 내부의 의존성 그래프입니다. 각 View의 프로퍼티(특히 @State, @ObservedObject)가 노드, "이 값이 바뀌면 어떤 View의 body를 다시 호출해야 하는가"가 엣지로 표현됩니다.

```swift
// 의사 그래프:
//
// @State count ──→ Text("카운트: \(count)")
//              └──→ if count > 10 { ... }
//
// count 변경 시:
// 1. count에 의존하는 노드들을 찾아 invalidate
// 2. 다음 렌더 사이클에 invalidated 노드만 다시 평가
// 3. 결과가 이전과 같으면 하위 트리 업데이트 스킵
```

### 왜 알면 좋나요?

"내 SwiftUI가 왜 느린가?"를 디버깅하려면 Attribute Graph 동작을 이해해야 합니다. 특히 **불필요한 body 재호출**이 성능 문제의 주범입니다.

### 흔한 성능 함정

```swift
// ❌ ExpensiveView가 매번 다시 그려짐!
struct ParentView: View {
    @State private var count = 0
    var body: some View {
        VStack {
            ExpensiveView()       // count 변경에도 영향받음
            Text("\\(count)")
            Button("+") { count += 1 }
        }
    }
}
// count 변경 → ParentView.body 재호출
// → 그 안의 ExpensiveView도 새로 생성됨
// → 비록 ExpensiveView 자체는 변경 없지만, init이 매번 호출됨
```

```swift
// ✅ 작은 View로 분리
struct ParentView: View {
    @State private var count = 0
    var body: some View {
        VStack {
            ExpensiveView()           // 입력 안 변하면 SwiftUI가 스킵
            CountDisplay(count: count) // count만 받음
            IncrementButton {
                count += 1
            }
        }
    }
}
// 각 View가 별개 struct → 입력이 같으면 body 호출 안 함
// (정확히는 호출은 되지만 결과 비교 후 UI 변경 안 함)
```

### EquatableView로 비교 최적화

```swift
struct ExpensiveView: View, Equatable {
    let data: SomeData
    
    var body: some View {
        // 복잡한 뷰
    }
    
    // 직접 동등성 정의
    static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.data.id == rhs.data.id
        // id만 같으면 동일 View로 간주 → 재계산 스킵
    }
}

// 사용
ExpensiveView(data: someData)
    .equatable()  // ← 이 modifier 추가
```

### 디버깅: body 호출 추적

```swift
// init에 print 추가하면 body 재호출 빈도 확인 가능
struct MyView: View {
    init() {
        print("MyView init")
    }
    
    let _ = Self._printChanges()  // iOS 15+: 무엇이 변경되어 재호출됐는지
    
    var body: some View {
        ...
    }
}
```

> 💡 **💡 면접 포인트:** "SwiftUI 성능 최적화의 핵심은 body 재호출 범위를 줄이는 것입니다. View를 작게 분리하고, 입력이 같은 경우 EquatableView로 명시하며, Self._printChanges()로 어떤 의존성이 변경되었는지 추적합니다. List의 셀에 무거운 ViewModel을 직접 넣지 말고 작은 표시 모델로 변환하는 것도 중요해요."


### 3. @State / @StateObject / @ObservedObject

_아이콘: `purple`_


### 3가지 상태 wrapper의 차이

### @State: View가 소유하는 값 타입 상태

```swift
struct CounterView: View {
    @State private var count = 0  // 항상 private!
    
    var body: some View {
        Text("\\(count)")
    }
}

// 특징:
// - 값 타입 (Int, String, Bool 등) 보관
// - View struct가 새로 생성되어도 값은 SwiftUI 내부 저장소에 유지됨
// - Attribute Graph에 등록되어 자동 재호출 트리거
// - private 권장 (외부 노출 X)
```

### @StateObject: View가 소유하는 참조 타입

```swift
class FeedViewModel: ObservableObject {
    @Published var items: [Item] = []
    
    func load() async { ... }
}

struct FeedView: View {
    @StateObject private var viewModel = FeedViewModel()
    
    var body: some View { ... }
}

// 특징:
// - View의 lifetime 동안 한 번만 생성!
// - View struct가 재생성되어도 같은 인스턴스 유지
// - ObservableObject 채택한 class만 가능
```

### @ObservedObject: 외부에서 주입받는 참조 타입

```swift
struct ChildView: View {
    @ObservedObject var viewModel: FeedViewModel  // 외부에서 받음
    
    var body: some View { ... }
}

// 특징:
// - View가 소유하지 않음 → View struct 재생성 시 새 인스턴스 가능!
// - ⚠️ 이게 가장 흔한 버그의 원인
```

### 가장 흔한 버그

```swift
// ❌ 잘못된 사용
struct ParentView: View {
    var body: some View {
        // 부모 body 재호출마다 새 ViewModel 생성!
        ChildView(viewModel: FeedViewModel())
        // → ChildView의 @ObservedObject가 매번 다른 인스턴스
        // → 상태가 계속 리셋됨!
    }
}

// ✅ 올바른 사용
struct ParentView: View {
    @StateObject private var viewModel = FeedViewModel()
    // 부모가 @StateObject로 소유 → 같은 인스턴스 유지
    
    var body: some View {
        ChildView(viewModel: viewModel)  // 같은 인스턴스 전달
    }
}
```

### 선택 가이드

| 상황 | 선택 |
|---|---|
| 간단한 값 타입 상태 (Int, String) | **@State** |
| ViewModel을 이 View가 처음 생성 | **@StateObject** |
| 상위 View에서 ViewModel 받기 | **@ObservedObject** |
| 앱 전역 상태 (테마, 사용자 정보) | **@EnvironmentObject** |
| 하위 View에 양방향 바인딩 | **@Binding** |

### @Published와 objectWillChange

```swift
class ViewModel: ObservableObject {
    @Published var name = ""
    // @Published가 자동으로 willSet 시점에 objectWillChange.send() 호출
    // (값 변경 직전!)
    
    var fullName: String { name }  // @Published 아님 → 변경 알림 안 감
}

// 수동 호출도 가능
class CustomViewModel: ObservableObject {
    var name = "" {
        willSet {
            objectWillChange.send()  // 직접 호출
        }
    }
}
```

> 💡 **💡 면접 포인트:** "@StateObject vs @ObservedObject 선택은 'View가 이 객체를 처음 생성하는가'로 결정합니다. 처음 생성하면 @StateObject(소유), 받기만 하면 @ObservedObject(참조). 부모에서 @ObservedObject로 ViewModel을 직접 만들어 자식에 넘기는 것은 매우 흔한 버그 패턴이니 주의해야 합니다."


### 4. List vs LazyVStack vs ForEach

_아이콘: `orange`_


### 대량 데이터 표시 시 선택지

### List: UITableView 기반, 가장 효율적

```swift
List(items) { item in
    ItemRow(item: item)
}

// 내부: UITableView + UIHostingCell
// 장점: 화면 밖 셀 자동 해제 (메모리 효율)
// 단점: 일부 커스터마이징 제한 (구분선, 셀 배경 등)
// 적합: 대량 데이터(100개+), 표 형태
```

### LazyVStack: 필요할 때만 생성, 해제 안 함

```swift
ScrollView {
    LazyVStack {
        ForEach(items) { item in
            ItemRow(item: item)
        }
    }
}

// 동작:
// - 화면 밖 항목은 처음엔 생성 안 함 (lazy)
// - 한 번 생성된 항목은 화면을 벗어나도 메모리에 남음
// 장점: 초기 로딩 빠름, 커스터마이징 자유
// 단점: 스크롤할수록 메모리 증가
// 적합: 중간 규모(50-200개), 자유로운 디자인
```

### VStack: 모두 즉시 생성

```swift
VStack {
    ForEach(items) { item in
        ItemRow(item: item)
    }
}

// 동작: 모든 항목을 한 번에 생성
// 적합: 소량 데이터(~20개), 항상 다 보이는 경우
```

### ForEach의 id 중요성

```swift
// 1. Hashable 기반
ForEach(items, id: \\.self) { item in
    Text(item)
}

// 2. Identifiable 기반 (권장)
struct Item: Identifiable {
    let id: String
    let name: String
}
ForEach(items) { item in  // id 자동 사용
    Text(item.name)
}

// 3. KeyPath 명시
ForEach(items, id: \\.id) { item in
    Text(item.name)
}

// id가 변경되면 → SwiftUI가 새 View로 간주 → 상태 리셋
// id가 유지되면 → 기존 View 업데이트 → 상태 유지
// 이 차이가 애니메이션 트리거 여부를 결정
```

### ScrollViewReader로 스크롤 제어

```swift
ScrollViewReader { proxy in
    ScrollView {
        LazyVStack {
            ForEach(messages) { message in
                MessageRow(message: message)
                    .id(message.id)
            }
        }
    }
    .onChange(of: messages.count) { _ in
        // 새 메시지 도착 시 자동 스크롤
        if let last = messages.last {
            withAnimation {
                proxy.scrollTo(last.id, anchor: .bottom)
            }
        }
    }
}
```

> 💡 **💡 면접 포인트:** "리스트 선택 기준은 데이터 규모와 메모리 동작입니다. 100개 이상이면 List(셀 재사용), 50개 정도이고 자유로운 디자인이 필요하면 LazyVStack, 20개 미만이면 일반 VStack이 적합합니다. ForEach의 id가 변경되면 View 재생성 + 애니메이션이 트리거된다는 점도 자주 활용하는 패턴이죠."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. @StateObject와 @ObservedObject의 차이는? `[기본 / 빈출]`

**@StateObject**: View가 소유. View의 lifetime 동안 한 번만 생성. View struct가 재생성되어도 같은 인스턴스 유지.

**@ObservedObject**: View가 소유 안 함. 외부에서 주입받음. View struct가 재생성될 때마다 다른 인스턴스를 받을 수 있음.

가장 흔한 버그: 부모에서 `ChildView(viewModel: ViewModel())`로 새 인스턴스를 생성해 자식에게 넘기면, 부모 body 재호출마다 자식 ViewModel이 리셋됩니다. 부모가 @StateObject로 소유한 후 전달해야 합니다.


### Q2. SwiftUI에서 body가 자주 호출되는 게 문제인가요? `[심화 / 빈출]`

body 호출 자체는 문제가 아닙니다. **body 안에서 무거운 작업을 하면 문제**입니다.

body는 \"새 View 트리를 만들어달라\"는 요청이고, 단순 struct 생성은 매우 빠릅니다. 문제는:
- body 안에서 네트워크 요청
- 복잡한 계산
- 큰 객체 매번 생성

해결:
1. View를 작은 단위로 분리 (변경 영향 범위 축소)
2. 무거운 작업은 onAppear, onChange로 이동
3. EquatableView로 불필요한 재계산 방지
4. Self._printChanges()로 호출 원인 추적


### Q3. @State와 @Binding의 관계는? `[기본 / 빈출]`

**@State**: 값을 소유. 한 View 안에서만 사용.
**@Binding**: 다른 View의 @State를 참조하여 양방향 동기화.

```swift
struct Parent: View {\n    @State private var text = \"\"\n    var body: some View {\n        Child(text: $text)  // $로 Binding 전달\n    }\n}\nstruct Child: View {\n    @Binding var text: String  // 부모의 text와 양방향 연결\n    var body: some View {\n        TextField(\"\", text: $text)\n        // 입력 시 부모의 text도 변경됨\n    }\n}
```
$ prefix는 'wrappedValue가 아닌 projectedValue를 가져온다'는 의미입니다.


### Q4. List와 LazyVStack은 메모리 동작이 어떻게 다른가요? `[심화 / 빈출]`

**List**: UITableView 기반. 화면 밖으로 나간 셀은 자동으로 메모리에서 해제되고, 화면에 들어올 때 다시 생성. 셀 재사용 메커니즘 활용.

**LazyVStack**: 처음엔 화면에 보이는 것만 생성(lazy). 하지만 한 번 생성되면 ScrollView가 살아있는 동안 계속 메모리에 남음. 스크롤할수록 메모리 사용량 증가.

그래서 100개 이상의 대량 데이터엔 List가 안전합니다. 단, List는 styling 자유도가 낮으므로 디자인 요구가 많으면 LazyVStack + 페이지네이션 조합이 대안입니다.


---


## ✏️ 퀴즈


### 문제 1

다음 코드의 문제점은?

```swift
struct Parent: View {\n  var body: some View {\n    Child(viewModel: MyViewModel())\n  }\n}\nstruct Child: View {\n  @ObservedObject var viewModel: MyViewModel\n  ...\n}
```


   **A.** @ObservedObject는 사용할 수 없는 키워드다

✅ **B.** Parent의 body 재호출마다 새 MyViewModel이 생성되어 상태가 리셋된다

   **C.** Child가 MyViewModel을 사용할 수 없다

   **D.** 컴파일 에러가 난다


**정답**: B


💡 **힌트**: @ObservedObject는 외부 의존성을 받기만 합니다. 누가 인스턴스를 소유하나요?


### 문제 2

SwiftUI에서 대량(500개+) 데이터를 표시할 때 가장 적합한 것은?


   **A.** VStack + ForEach

   **B.** LazyVStack + ForEach

✅ **C.** List

   **D.** HStack + ForEach


**정답**: C


💡 **힌트**: 화면 밖 항목 메모리 자동 해제가 중요합니다.


