# Day 5 — RunLoop / UI 업데이트 메커니즘

**태그**: RunLoop · UI Update Cycle · Layout Cycle · Display Cycle · CADisplayLink · Main Thread · CATransaction

---

## 📝 핵심 정리

## 1. RunLoop과 UI 업데이트 사이클

### RunLoop의 정체

RunLoop은 **스레드가 할 일이 없을 때는 잠들어 있다가, 이벤트나 타이머 같은 작업이 들어오면 깨어나서 처리하고 다시 대기하는 이벤트 처리 루프**입니다.

스레드는 기본적으로 코드를 실행하고 끝나면 종료됩니다. 하지만 iOS 앱의 Main Thread는 앱이 살아있는 동안 계속 사용자 입력, Timer, Source, 화면 갱신 요청을 처리해야 합니다. 이때 Main Thread가 종료되지 않고 계속 이벤트를 받을 수 있게 만드는 구조가 Main RunLoop입니다.

```swift
// 개념적인 의사 코드
while appIsRunning {
    waitForEvent()                  // mach_msg로 커널에서 대기 (CPU 사용 안 함)

    handleInputSources()            // Source 0 / Source 1
    fireTimers()
    executeMainQueueBlocks()

    processLayoutIfNeeded()
    processDisplayIfNeeded()
    commitCoreAnimationTransaction()

    sleepUntilNextEvent()
}
```

중요한 점은 RunLoop이 단순히 코드를 "한 번 실행하는 단위"가 아니라는 것입니다. RunLoop은 **이벤트를 기다리고, 처리하고, 화면 갱신을 commit하고, 다시 잠드는 반복 구조**입니다.

### RunLoop의 한 사이클

RunLoop 한 사이클에서 처리하는 것들:

| 단계 | 처리 대상 |
|---|---|
| Source 0 | `performSelector`, 터치 이벤트 등 (port-based가 아닌 것) |
| Source 1 | port-based 시스템 이벤트 |
| Timer | 등록된 Timer fire |
| Observer | beforeWaiting, afterWaiting 등 lifecycle hook |
| Main Queue 작업 | `DispatchQueue.main.async`로 예약된 block |
| Layout / Display | 더티 상태인 View들의 layout pass, display pass |
| CA Commit | Core Animation transaction을 Render Server로 전달 |
| 대기 | `mach_msg`로 커널에서 새 이벤트 대기 |

### UI 업데이트가 즉시 화면에 반영되지 않는 이유

UIKit에서 다음 코드를 실행했다고 해서 화면 픽셀이 즉시 바뀌는 것은 아닙니다.

```swift
titleLabel.text = "Loading"
titleLabel.text = "Complete"
```

`titleLabel.text` 프로퍼티 값은 각 라인이 실행되는 즉시 메모리상에서 변경됩니다. 하지만 실제 화면 반영은 보통 Main RunLoop의 layout/display update cycle과 Core Animation commit 이후에 이루어집니다.

즉, 위 코드에서는 `"Loading"`이 메모리상 값으로 잠깐 들어갔다가 바로 `"Complete"`로 덮이고, 실제 화면에는 최종 값인 `"Complete"`만 보일 가능성이 높습니다.

```text
프로퍼티 값 변경
→ 즉시 메모리상 상태 변경

실제 화면 반영
→ 다음 layout/display cycle
→ Core Animation transaction commit
→ Render Server / GPU
→ 다음 frame에 표시
```

UIKit은 여러 UI 변경을 매번 즉시 그리지 않고, 같은 cycle 안에서 발생한 변경을 병합해서 처리할 수 있습니다.

```swift
@objc private func didTapButton() {
    titleLabel.text = "A"

    DispatchQueue.main.async {
        self.titleLabel.text = "B"
    }

    titleLabel.text = "C"
}
```

실행 순서는 `A → C → B`이고, 화면에는 보통 최종 값인 `"B"`만 보입니다. `DispatchQueue.main.async`는 Main Thread에서 호출해도 즉시 실행되지 않고, 현재 Main Queue 작업이 끝난 뒤 실행됩니다.

> **최종 핵심 문장**: UIKit의 UI 변경은 메모리상 상태 변경은 즉시 일어나지만, 실제 화면 반영은 Main RunLoop의 layout/display cycle과 Core Animation transaction commit 이후에 이루어집니다.

### RunLoop Mode와 Timer 함정

RunLoop은 한 번에 하나의 mode로 동작합니다. mode마다 처리 대상이 되는 source, timer, observer가 다릅니다.

| Mode | 의미 |
|---|---|
| `.default` | 일반적인 앱 동작 상태 |
| `.tracking` | `UIScrollView` 드래그처럼 터치를 추적하는 상태 |
| `.common` | `.default`, `.tracking` 등에 공통으로 포함될 수 있는 mode 집합 |

대표적인 함정은 `Timer.scheduledTimer`입니다.

```swift
timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
    print("tick")
}
```

`scheduledTimer`는 기본적으로 `.default` mode에 등록됩니다. 사용자가 `UIScrollView`를 드래그하면 Main RunLoop이 `.tracking` mode로 전환되고, `.default` mode에만 등록된 Timer는 fire되지 않습니다.

```text
일반 상태
→ RunLoop default mode → Timer 동작

스크롤 드래그 중
→ RunLoop tracking mode → default mode Timer는 실행되지 않음
```

스크롤 중에도 Timer가 동작해야 한다면 `.common` mode에 등록합니다.

```swift
let timer = Timer(timeInterval: 1.0, repeats: true) { [weak self] _ in
    self?.countLabel.text = "\(Date())"
}
RunLoop.main.add(timer, forMode: .common)
```

스크롤 자체는 60fps 이상의 부드러움이 필요해서 다른 무거운 작업이 끼어들면 안 됩니다. 그래서 시스템이 의도적으로 `.tracking` 모드에서 일반 Timer를 멈추는 것입니다. `.common`에 등록하면 스크롤 중에도 실행되므로 작업이 무겁다면 오히려 스크롤 성능을 해칠 수 있습니다.

> 면접 포인트: Timer가 스크롤 중 멈추는 이유는 Main Thread가 반드시 바빠서가 아니라, Timer가 등록된 RunLoop mode와 현재 RunLoop mode가 다르기 때문입니다.

---

## 2. UI Layout Cycle

### Layout Cycle의 역할

Layout Cycle은 View의 크기와 위치를 계산하는 과정입니다. 대표 메서드는 세 가지입니다.

| 메서드 | 역할 |
|---|---|
| `setNeedsLayout()` | 다음 layout pass에서 다시 배치가 필요하다고 표시 |
| `layoutIfNeeded()` | layout이 필요한 상태라면 즉시 layout pass 수행 |
| `layoutSubviews()` | 실제 subview frame 배치가 일어나는 UIView 메서드 |

### setNeedsLayout()

`setNeedsLayout()`은 즉시 `layoutSubviews()`를 호출하지 않습니다. 대신 해당 View의 layout이 더 이상 유효하지 않으니 다음 layout pass에서 다시 계산해야 한다고 표시합니다.

```swift
view.setNeedsLayout()
view.setNeedsLayout()
view.setNeedsLayout()
```

같은 RunLoop cycle 안에서 여러 번 호출해도 일반적으로 layout pass는 병합되어 한 번만 수행될 수 있습니다. "3번 호출했으니 `layoutSubviews()`도 3번 호출된다"는 잘못된 설명입니다.

### layoutSubviews()

`layoutSubviews()`는 실제로 subview들의 frame을 배치하는 메서드입니다. 개발자가 직접 호출하기보다는 UIKit이 layout pass 중에 호출합니다.

```swift
final class ProfileView: UIView {
    private let nameLabel = UILabel()

    override func layoutSubviews() {
        super.layoutSubviews()
        nameLabel.frame = bounds.insetBy(dx: 16, dy: 8)
    }
}
```

`layoutSubviews()`가 호출될 수 있는 대표 상황:

```text
bounds 변경
subview 추가 / 제거
constraint 변경
setNeedsLayout() 이후 layout pass 도달
layoutIfNeeded()로 즉시 layout 강제
```

주의할 점은 `layoutSubviews()` 안에서 조건 없이 `setNeedsLayout()`을 호출하면 안 된다는 것입니다.

```swift
override func layoutSubviews() {
    super.layoutSubviews()
    label.frame = bounds.insetBy(dx: 8, dy: 4)

    setNeedsLayout()  // ❌ 위험: layout loop 가능
}
```

방어가 필요하다면 상태 변경 여부를 비교해야 합니다.

```swift
private var previousBounds: CGRect = .zero

override func layoutSubviews() {
    super.layoutSubviews()
    label.frame = bounds.insetBy(dx: 8, dy: 4)

    guard previousBounds != bounds else { return }
    previousBounds = bounds
    // 정말 필요한 추가 처리만
}
```

### layoutIfNeeded()

`layoutIfNeeded()`는 항상 layout을 강제로 수행하는 메서드가 아닙니다. 정확히는 **현재 View hierarchy에 layout이 필요한 상태라면 즉시 layout pass를 수행**합니다.

```swift
func updateName(_ name: String) {
    nameLabel.text = name
    setNeedsLayout()
    layoutIfNeeded()  // 직전에 dirty 상태가 됐으므로 즉시 layoutSubviews() 호출
}
```

layout이 필요한 상태가 아니라면 `layoutIfNeeded()`는 별다른 일을 하지 않을 수 있습니다.

### ViewController Lifecycle과 Layout Cycle

```text
viewDidLoad()
→ viewWillAppear()
→ viewWillLayoutSubviews()
→ view.layoutSubviews()
→ viewDidLayoutSubviews()
→ viewDidAppear()
```

`viewDidLoad`는 View가 메모리에 올라온 시점이라 subview 추가, constraint 설정, 초기 바인딩에 적합하지만, 최종 frame이 확정되었다고 가정하면 안 됩니다.

```swift
override func viewDidLoad() {
    super.viewDidLoad()
    print(view.bounds.width)  // ⚠️ 최종값이 아닐 수 있음
}
```

Frame이나 safeArea 기반 후처리는 `viewDidLayoutSubviews()` 이후가 더 안전합니다. 단, 여러 번 호출될 수 있으므로 일회성 작업은 flag로 방어해야 합니다.

### Constraint Animation에서 layoutIfNeeded를 쓰는 이유

Constraint는 화면에 직접 그려지는 값이 아니라 Auto Layout의 입력값입니다. 실제로 화면에서 애니메이션되는 것은 constraint 자체가 아니라, constraint 변경 결과로 계산된 frame 또는 backing layer의 bounds/position입니다.

```swift
@objc private func didTapButton() {
    view.layoutIfNeeded()         // 1. 시작 layout 확정
    heightConstraint.constant = 200 // 2. constraint 변경

    UIView.animate(withDuration: 0.3) {
        self.view.layoutIfNeeded()  // 3. 변경된 constraint를 frame 변화로 commit
    }
}
```

```text
1. 현재 layout 상태 확정
2. constraint constant 변경
3. animation block 안에서 layoutIfNeeded()
4. 변경된 constraint 기준으로 frame 계산
5. frame / layer property 변화가 animation transaction에 포함
6. 시작 frame → 종료 frame으로 보간
```

반대로 `UIView.animate { self.heightConstraint.constant = 200 }`는 자연스럽게 애니메이션되지 않을 수 있습니다. constant만 바꿨을 뿐 새 constraint 결과를 frame 변화로 계산시키는 layout pass가 animation transaction 안에서 일어나지 않을 수 있기 때문입니다.

### layoutIfNeeded는 어느 View에 호출해야 하나요?

> 변경된 constraint를 포함하고, 실제로 다시 배치해야 하는 View들의 **가장 가까운 공통 상위 View**에 `layoutIfNeeded()`를 호출하는 것이 적절합니다.

`boxView`가 `containerView`의 subview이고 `boxView`의 height constraint를 바꾼다면, `boxView.layoutIfNeeded()`보다 `containerView.layoutIfNeeded()`가 더 적절합니다. `boxView` 자신의 frame은 자기 자신이 아니라 superview의 layout 과정에서 결정되기 때문입니다.

```swift
heightConstraint.constant = 200

UIView.animate(withDuration: 0.3) {
    self.containerView.layoutIfNeeded()
}
```

---

## 3. Display Cycle (setNeedsDisplay vs setNeedsLayout)

### Display Cycle의 역할

Layout Cycle이 View의 위치와 크기를 계산한다면, Display Cycle은 View의 **그림 내용**을 다시 그립니다.

| 메서드 | 연결되는 작업 | 사용 상황 |
|---|---|---|
| `setNeedsLayout()` | `layoutSubviews()` | subview 위치/크기 변경 |
| `setNeedsDisplay()` | `draw(_:)` | 직접 그리는 내용 변경 |

### setNeedsDisplay()

`setNeedsDisplay()`는 View의 drawing contents가 변경되었으니 다음 drawing cycle에서 다시 그려달라고 표시하는 메서드입니다.

```swift
final class GraphView: UIView {
    var points: [CGPoint] = [] {
        didSet { setNeedsDisplay() }
    }

    override func draw(_ rect: CGRect) {
        super.draw(rect)
        // points 기반 그래프 그리기
    }
}
```

`points`가 바뀌면 바로 `draw(_:)`가 호출되는 것이 아닙니다.

```text
points 변경
→ setNeedsDisplay()
→ display dirty 상태 표시
→ 다음 drawing cycle에서 draw(_:) 호출
→ layer contents 반영
→ 화면 표시
```

같은 RunLoop cycle 안에서 `points`가 여러 번 바뀌어도 `draw(_:)`가 매번 즉시 호출되는 것은 아닙니다. 일반적으로 마지막 상태 기준으로 한 번 그려질 가능성이 높습니다.

### ProgressBar 예시 — 둘의 구분 기준

`ProgressBarView`가 `draw(_:)`에서 직접 bar를 그린다면 `progress` 변경 시 `setNeedsDisplay()`가 맞습니다.

```swift
final class ProgressBarView: UIView {
    var progress: CGFloat = 0 {
        didSet { setNeedsDisplay() }
    }

    override func draw(_ rect: CGRect) {
        super.draw(rect)
        // progress 값에 따라 bar를 직접 그림
    }
}
```

반대로 ProgressBar가 내부 `barView`의 width constraint나 frame으로 구현되어 있다면 layout 변경입니다.

```swift
var progress: CGFloat = 0 {
    didSet {
        barWidthConstraint.constant = bounds.width * progress
        setNeedsLayout()
    }
}
```

기준은 명확합니다.

```text
직접 drawing 기반        → setNeedsDisplay()
subview frame / constraint 기반 → setNeedsLayout() 또는 layoutIfNeeded()
```

---

## 4. 왜 UI는 Main Thread에서만?

### UIKit이 thread-safe하지 않다는 의미

thread-safe하다는 것은 여러 스레드가 동시에 접근해도 객체의 상태가 깨지지 않도록 내부적으로 보호되어 있다는 뜻입니다. UIKit은 대부분 thread-safe하지 않습니다.

```swift
DispatchQueue.global().async {
    self.label.text = "A"  // ⚠️ 위험
}

DispatchQueue.main.async {
    self.label.text = "B"
}
```

`label.text` 변경은 단순 문자열 대입처럼 보이지만 실제로는 여러 내부 상태 변경으로 이어집니다.

```text
text 변경
→ intrinsicContentSize 변경 가능
→ layout invalidation 필요
→ display invalidation 필요
→ CALayer contents 갱신 필요
```

이 과정에서 한 스레드는 layout 계산 중인데 다른 스레드가 frame이나 constraint를 바꾸면 UIKit 내부 상태의 일관성이 깨질 수 있습니다.

### 왜 thread-safe하게 만들지 않았나요?

핵심은 **성능**입니다. 모든 UI 객체를 아무 스레드에서나 안전하게 수정할 수 있게 만들려면 UIKit 내부의 많은 상태 접근에 lock 같은 동기화 장치가 필요합니다.

```swift
lock.lock()
label.text = "A"
updateIntrinsicContentSize()
markNeedsLayout()
markNeedsDisplay()
lock.unlock()
```

UI 작업은 매우 자주 발생합니다. 스크롤이나 애니메이션 중에는 한 프레임 안에 cell 재사용, label text 변경, image 변경, constraint 계산, frame 변경, layer property 변경 등이 매우 많이 발생합니다. 60fps 기준 한 프레임 예산은 약 16.67ms이고, 이 시간 안에 이벤트 처리, layout, display, commit까지 끝내야 합니다.

모든 UI 접근마다 lock을 걸면 동기화 비용이 누적되어 프레임 유지에 불리합니다. 그래서 UIKit은 다음 설계를 선택했습니다.

```text
모든 UI API를 thread-safe하게 만든다
→ 안전하지만 무겁다

UI는 Main Thread에서만 접근한다는 규칙을 둔다
→ lock 비용을 줄이고 빠르게 동작한다
```

UIKit은 안전을 내부 lock으로 해결하기보다 **Main Thread 단일 접근 규칙**으로 해결하는 구조입니다.

### Main Thread block과 UI 반영

Main Thread에서 오래 걸리는 작업을 하면 UI 변경이 화면에 반영되지 못합니다.

```swift
@objc private func didTapButton() {
    titleLabel.text = "Loading"
    Thread.sleep(forTimeInterval: 3)
    titleLabel.text = "Complete"
}
```

`"Loading"`은 메모리상 값으로는 즉시 들어가지만, 바로 Main Thread가 3초 동안 block됩니다. RunLoop이 layout/display cycle을 처리할 수 없으므로 사용자는 `"Loading"`을 보지 못하고 `"Complete"`만 볼 가능성이 높습니다.

반대로 무거운 작업을 background queue로 보내면 Main Thread는 계속 update cycle을 돌 수 있습니다.

```swift
@objc private func didTapButton() {
    titleLabel.text = "Loading"

    DispatchQueue.global(qos: .userInitiated).async {
        Thread.sleep(forTimeInterval: 3)
        DispatchQueue.main.async {
            self.titleLabel.text = "Complete"
        }
    }
}
```

`asyncAfter`도 Main Thread를 block하지 않습니다.

```swift
DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
    self.titleLabel.text = "Complete"
}
```

`asyncAfter`는 3초 동안 Main Thread를 멈추는 것이 아니라, 지정한 deadline 이후 Main Queue에 block을 enqueue합니다.

```text
Thread.sleep                        → 현재 스레드를 실제로 멈춤
DispatchQueue.main.asyncAfter      → 현재 스레드는 멈추지 않고 작업 실행 시점만 예약
```

### 동기 네트워크 + 로딩 인디케이터 함정

```swift
@objc private func didTapButton() {
    loadingView.isHidden = false
    let result = requestSynchronously()       // Main Thread block!
    titleLabel.text = result.title
    loadingView.isHidden = true
}
```

```text
loadingView.isHidden = false
→ 로딩뷰가 보여야 하는 상태가 됨
→ requestSynchronously()가 Main Thread block
→ RunLoop이 화면 업데이트를 못 함
→ 요청 완료
→ loadingView.isHidden = true
→ 최종 상태만 화면에 반영
```

개선은 네트워크 작업은 비동기, UI 업데이트만 Main Thread 또는 MainActor에서 처리하는 것입니다.

```swift
@objc private func didTapButton() {
    loadingView.isHidden = false

    Task {
        do {
            let result = try await request()
            await MainActor.run {
                self.titleLabel.text = result.title
                self.loadingView.isHidden = true
            }
        } catch {
            await MainActor.run {
                self.loadingView.isHidden = true
            }
        }
    }
}
```

> 면접 답변: UIKit은 대부분 thread-safe하지 않습니다. UI 변경은 단순히 프로퍼티 하나를 바꾸는 것이 아니라 View hierarchy, Auto Layout, CALayer 상태 변경까지 이어집니다. 이 상태들이 여러 스레드에서 동시에 변경되면 UIKit 내부 상태의 일관성이 깨질 수 있어 UI 업데이트는 Main Thread에서 직렬적으로 처리해야 합니다. 모든 UI 접근에 lock을 걸면 동기화 비용이 60fps frame budget에 불리하므로, UIKit은 "UI는 Main Thread에서만 접근한다"는 규칙으로 빠르게 동작하도록 설계되어 있습니다.

---

## 5. CADisplayLink와 Frame Budget

### CADisplayLink란?

`CADisplayLink`는 Timer처럼 단순 시간 간격으로 동작하는 것이 아니라, 디스플레이 refresh 타이밍에 맞춰 selector를 호출하는 객체입니다.

```text
Timer            → 정해진 시간 간격마다 실행
CADisplayLink    → 화면이 다시 그려질 타이밍마다 실행
```

따라서 프레임 단위 애니메이션, 게임 루프, progress 업데이트, 커스텀 drawing 업데이트에 적합합니다.

```swift
displayLink = CADisplayLink(target: self, selector: #selector(updateFrame))
displayLink.add(to: .main, forMode: .common)

@objc private func updateFrame(_ link: CADisplayLink) {
    progressView.progress += 0.01
}
```

### CADisplayLink와 RunLoop Mode

`CADisplayLink`도 RunLoop에 등록되어 동작하므로 어떤 mode에 등록했는지가 중요합니다. `.default`에만 등록하면 스크롤 중 Main RunLoop이 `.tracking` mode로 전환될 때 callback이 멈출 수 있습니다. 스크롤 중에도 호출되어야 한다면 `.common`에 등록합니다.

```swift
displayLink.add(to: .main, forMode: .common)
```

### 60fps와 120fps Frame Budget

| 디스플레이 | 주파수 | 한 프레임 예산 |
|---|---:|---:|
| 일반 디스플레이 | 60Hz | 약 16.67ms |
| ProMotion | 120Hz | 약 8.33ms |

60fps 기준으로 한 프레임 안에 다음 작업들이 끝나야 합니다.

```text
이벤트 처리
→ 애니메이션 상태 업데이트
→ layout
→ display
→ Core Animation commit
→ Render Server / GPU 처리
```

`CADisplayLink` callback 안에서 무거운 작업을 수행하면 Main Thread가 점유되어 다음 frame을 제때 준비하지 못합니다.

```swift
@objc private func updateFrame() {
    heavyCalculation()  // ❌ 오래 걸리면 프레임 드랍
    progressView.progress += 0.01
}
```

결과: 프레임 드랍, 애니메이션 끊김, 스크롤 버벅임, 터치 반응 지연.

개선 방향:

```text
CADisplayLink callback에서는 최소 상태 반영만 수행
무거운 계산은 background queue에서 미리 처리
계산 결과 캐싱
매 프레임 전체 계산 금지
timestamp 기반 업데이트 사용
```

Frame count 기반 증가는 refresh rate에 따라 속도가 달라질 수 있으므로 timestamp delta 기반이 안전합니다.

```swift
private var lastTimestamp: CFTimeInterval = 0
private var progress: CGFloat = 0

@objc private func updateFrame(_ link: CADisplayLink) {
    if lastTimestamp == 0 {
        lastTimestamp = link.timestamp
        return
    }

    let deltaTime = link.timestamp - lastTimestamp
    lastTimestamp = link.timestamp

    progress += CGFloat(deltaTime) * 0.3
    progressView.progress = min(progress, 1.0)
}
```

### ProMotion 지원

ProMotion 디바이스에서 120fps를 활용하려면 `preferredFrameRateRange`를 명시해야 합니다. 미명시 시 기본값은 60fps로 제한됩니다.

```swift
displayLink.preferredFrameRateRange = CAFrameRateRange(
    minimum: 60, maximum: 120, preferred: 120
)
```

게임이나 애니메이션 외에 일반 작업에 CADisplayLink를 쓰지 마세요. 매 프레임마다 깨워서 배터리 소모가 큽니다.

---

## 💬 꼬리 질문 & 면접 답변

### Q1. UIKit의 UI 업데이트는 왜 즉시 화면에 반영되지 않나요?

UIKit에서 UI 프로퍼티를 변경하면 객체의 상태는 즉시 바뀌지만, 실제 화면 반영은 즉시 일어나지 않습니다. UIKit은 변경된 View를 layout 또는 display가 필요한 상태로 표시하고, Main RunLoop의 update cycle에서 layout pass와 display pass를 처리합니다. `setNeedsLayout()`은 다음 layout pass를 예약하는 것이고, `layoutSubviews()`는 실제 frame 계산이 일어나는 지점입니다. 이후 Core Animation transaction이 RunLoop의 commit 시점에 Render Server로 전달되고, 다음 frame에 실제 화면으로 표시됩니다. 그래서 여러 UI 변경은 같은 cycle 안에서 병합될 수 있고, 중간 상태가 아니라 최종 상태만 화면에 보일 수 있습니다.

---

### Q2. `DispatchQueue.main.async`를 썼는데도 Loading이 안 보이는 이유는?

`titleLabel.text = "Loading"`은 즉시 메모리상 값을 변경합니다. 하지만 실제 화면 반영은 RunLoop update cycle과 CA transaction commit 이후에 일어납니다. `DispatchQueue.main.async` block은 현재 메서드 실행이 끝난 뒤 Main Queue에서 실행됩니다. 이 block이 화면 commit 전에 실행되면 `"Loading"`이 화면에 그려지기 전에 `"Complete"`로 덮일 수 있어, 사용자는 최종 값만 볼 가능성이 높습니다.

---

### Q3. Main Thread에서 `Thread.sleep`을 호출하면 왜 문제가 되나요?

`"Loading"` 값은 메모리상 즉시 들어가지만, Main Thread가 sleep으로 block되면 RunLoop이 layout/display cycle을 처리할 수 없습니다. 따라서 `"Loading"`은 실제 화면에 표시되지 못하고, sleep 이후 `"Complete"`로 변경된 최종 상태만 반영됩니다. Main Thread가 block되는 동안 터치, 스크롤, 애니메이션도 멈춥니다.

---

### Q4. `setNeedsLayout()`과 `layoutIfNeeded()`의 차이는?

`setNeedsLayout()`은 layout이 필요하다는 표시만 하고 즉시 layout을 수행하지 않습니다. 같은 RunLoop cycle 안에서 여러 번 호출되면 병합될 수 있습니다. `layoutIfNeeded()`는 현재 layout이 필요한 상태라면 즉시 layout pass를 수행합니다. 그래서 constraint 변경 후 animation block 안에서 호출하면 Auto Layout 결과로 계산된 frame 변화가 animation transaction에 포함되어 부드러운 애니메이션이 됩니다.

---

### Q5. Constraint Animation에서 실제로 애니메이션되는 것은 constraint인가요?

아닙니다. Constraint는 Auto Layout의 입력값입니다. 실제로 애니메이션되는 것은 constraint 변경 결과로 계산된 frame, 더 정확히는 backing layer의 bounds, position 같은 animatable property입니다. constraint constant 변경 → Auto Layout이 새 frame 계산 → CALayer bounds/position 변화 → Core Animation이 layer property 변화 보간 순서입니다.

---

### Q6. `layoutSubviews()` 안에서 `setNeedsLayout()`을 호출하면 왜 위험한가요?

`layoutSubviews()`는 layout pass 중에 호출되는 메서드입니다. 그 내부에서 조건 없이 `setNeedsLayout()`을 호출하면 layout이 끝나는 시점에 다시 layout이 필요하다고 표시하게 됩니다. 다음 layout cycle에서 `layoutSubviews()`가 반복 호출될 수 있고, 심하면 layout loop나 성능 저하가 발생합니다.

---

### Q7. `setNeedsDisplay()`와 `setNeedsLayout()`은 어떻게 구분하나요?

`setNeedsLayout()`은 subview의 위치나 크기 재계산이 필요할 때 사용하며 `layoutSubviews()`와 연결됩니다. `setNeedsDisplay()`는 직접 그리는 내용이 바뀌었을 때 사용하며 `draw(_:)`와 연결됩니다. bar를 `draw(_:)`에서 직접 그리면 setNeedsDisplay, barView의 width constraint로 표현하면 setNeedsLayout/layoutIfNeeded.

---

### Q8. 스크롤 중 Timer나 CADisplayLink가 멈추는 이유는?

`Timer.scheduledTimer`나 `.default` mode에 등록된 `CADisplayLink`는 기본적으로 RunLoop의 `.default` mode에서만 동작합니다. `UIScrollView`를 드래그하면 Main RunLoop이 터치 추적을 위해 `.tracking` mode로 전환되고, 이때 `.default` mode에만 등록된 객체는 실행 대상이 아니므로 멈춘 것처럼 보입니다. 스크롤 중에도 동작해야 한다면 `.common` mode에 등록합니다.

---

### Q9. CADisplayLink callback에서 무거운 작업을 하면 어떻게 되나요?

`CADisplayLink`는 display refresh 타이밍에 맞춰 Main RunLoop에서 호출됩니다. 60fps 기준 한 프레임 예산은 약 16.67ms이고, 이 시간 안에 이벤트 처리, 애니메이션 업데이트, layout, display, Core Animation commit까지 끝나야 합니다. callback 안에서 무거운 계산을 수행하면 Main Thread가 점유되어 다음 frame을 제때 준비하지 못하고, 프레임 드랍이나 스크롤 버벅임이 발생합니다. callback에서는 최소한의 상태 반영만 하고, 무거운 계산은 background에서 처리하거나 캐싱해야 합니다.

---

### Q10. `DispatchQueue.main.asyncAfter`는 Main Thread를 block하나요?

아닙니다. `asyncAfter`는 지정한 deadline 이후 Main Queue에 block을 enqueue할 뿐, 현재 스레드를 멈추지 않습니다. `Thread.sleep`은 실제로 스레드를 block하지만, `asyncAfter`는 작업 실행 시점만 예약합니다. 그래서 `asyncAfter` 호출 후에도 Main Thread는 RunLoop을 계속 돌면서 다른 이벤트와 layout/display cycle을 처리할 수 있습니다.

---

## ✏️ 퀴즈

### 문제 1

다음 코드에서 실제 화면에 보일 가능성이 가장 높은 값은?

```swift
titleLabel.text = "Loading"
titleLabel.text = "Complete"
```

- A. Loading
- B. Complete
- C. 둘 다 순서대로 보인다
- D. 아무것도 보이지 않는다

**정답: B**

💡 **힌트**: 프로퍼티 값 변경은 즉시지만, 실제 화면 반영은 update cycle 이후입니다.

---

### 문제 2

다음 코드의 실행 순서는?

```swift
titleLabel.text = "A"

DispatchQueue.main.async {
    titleLabel.text = "B"
}

titleLabel.text = "C"
```

- A. A → B → C
- B. A → C → B
- C. B → A → C
- D. 순서를 알 수 없다

**정답: B**

💡 **힌트**: `main.async`는 현재 Main Queue 작업이 끝난 뒤 실행됩니다.

---

### 문제 3

`setNeedsLayout()`을 3번 연속 호출하면 `layoutSubviews()`도 반드시 3번 호출된다.

- A. 맞다
- B. 아니다
- C. 동기 호출일 때만 그렇다
- D. 디바이스 성능에 따라 다르다

**정답: B**

💡 **힌트**: `setNeedsLayout()`은 dirty flag를 세우는 방식이며, 같은 cycle 내 요청은 병합됩니다.

---

### 문제 4

Constraint 변경 애니메이션에서 실제로 애니메이션되는 것은?

- A. constraint constant 자체
- B. constraint 변경 결과로 계산된 frame / layer property
- C. Auto Layout equation
- D. NSLayoutConstraint 객체

**정답: B**

---

### 문제 5

스크롤 중 Timer가 멈추는 대표적인 이유는?

- A. Main Thread가 항상 block되기 때문
- B. Timer가 `.default` mode에 등록되어 있고 RunLoop이 `.tracking` mode로 전환되기 때문
- C. Timer는 스크롤 중 원래 사용할 수 없기 때문
- D. Timer가 background thread에서만 동작하기 때문

**정답: B**

---

### 문제 6

`draw(_:)`에서 직접 그래프를 그리는 View의 데이터가 바뀌었다면 무엇을 호출하는 게 적절한가?

- A. setNeedsLayout()
- B. setNeedsDisplay()
- C. layoutSubviews()
- D. layoutIfNeeded()

**정답: B**

---

### 문제 7

60Hz 디스플레이에서 한 프레임 예산은 대략 얼마인가?

- A. 8.33ms
- B. 16.67ms
- C. 33.33ms
- D. 60ms

**정답: B**

---

### 문제 8

`DispatchQueue.main.asyncAfter(deadline: .now() + 3)`은 Main Thread를 3초 동안 block한다.

- A. 맞다
- B. 아니다
- C. 디바이스에 따라 다르다
- D. iOS 15부터 block된다

**정답: B**

💡 **힌트**: 작업 실행 시점을 예약할 뿐 현재 스레드를 멈추지 않습니다.

---

## 🔚 마무리 요약

- UI 프로퍼티 값은 즉시 바뀌지만, 실제 화면 반영은 RunLoop update cycle 이후에 일어난다.
- UIKit은 변경된 View를 layout/display dirty 상태로 표시하고, 같은 cycle의 여러 변경을 병합할 수 있다.
- `setNeedsLayout()`은 예약, `layoutIfNeeded()`는 필요 시 즉시 layout pass 수행, `layoutSubviews()`는 실제 frame 배치 지점이다.
- `setNeedsDisplay()`는 직접 drawing contents가 바뀌었을 때 사용하고, `draw(_:)`와 연결된다.
- UIKit은 thread-safe하지 않으므로 UI는 Main Thread에서 직렬적으로 처리해야 한다.
- Main Thread를 block하면 Loading UI, animation, scroll, touch response가 모두 지연될 수 있다.
- Timer와 CADisplayLink는 RunLoop mode의 영향을 받는다.
- CADisplayLink callback에서는 frame budget을 넘기지 않도록 최소 작업만 해야 한다.
