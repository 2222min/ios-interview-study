# Day 5 — RunLoop / UI 업데이트 메커니즘

**태그**: RunLoop · CADisplayLink · Layout Cycle · Main Thread · CATransaction

---

## 📝 핵심 정리


### 1. RunLoop이 뭔가요?

_아이콘: `blue`_


### RunLoop의 정체

"이벤트가 들어올 때까지 대기하다가, 들어오면 처리하고, 다시 대기"를 무한 반복하는 루프입니다. 각 스레드마다 하나씩 가질 수 있고, 메인 스레드의 RunLoop은 앱이 켜질 때 자동으로 시작됩니다.

### 왜 필요한가요?

스레드는 기본적으로 코드를 실행하고 끝나면 종료됩니다. 하지만 메인 스레드는 앱이 살아있는 동안 계속 이벤트(터치, 네트워크 응답, 타이머)를 받아야 합니다. RunLoop이 이 무한 대기-처리 사이클을 만듭니다.

```swift
// 의사 코드:
while (앱이 살아있는 동안) {
    이벤트 도착 대기
    이벤트 받으면 처리:
        - 터치 이벤트
        - Timer fire
        - 네트워크 콜백
        - perform selector
        - draw 요청
    화면 갱신 필요하면 layout/draw/commit
    다시 대기
}
```

### RunLoop의 한 사이클

- **Source 0 처리**: performSelector, 터치 이벤트 등 (port-based가 아닌 것)

- **Source 1 처리**: port-based 시스템 이벤트

- **Timer fire 처리**

- **Observer 알림**: beforeWaiting, afterWaiting 등 lifecycle hook

- **대기**: `mach_msg`로 커널에서 새 이벤트 대기 (CPU 사용 안 함)

### RunLoop Mode

RunLoop은 한 번에 하나의 mode로 동작합니다. mode마다 처리하는 source/timer가 다릅니다.

| Mode | 언제 |
|---|---|
| `.default` | 일반 상태 |
| `.tracking` | UIScrollView 스크롤 중 (터치 추적) |
| `.common` | .default + .tracking 모두 포함하는 가상 mode |

### 유명한 함정: Timer가 스크롤 중에 멈춤

```swift
// ❌ 스크롤 중에 Timer가 안 동작!
let timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
    print("tick")
}
// scheduledTimer는 기본적으로 .default 모드에 등록
// 사용자가 스크롤 시작 → RunLoop이 .tracking 모드로 전환 → Timer 멈춤!

// ✅ 해결: .common 모드에 추가
RunLoop.main.add(timer, forMode: .common)
// .common은 .default + .tracking을 포함하므로 항상 동작
```

### 왜 모드를 분리했나요?

스크롤은 60fps 이상의 부드러움이 필요해서 다른 작업이 끼어들면 안 됩니다. 그래서 시스템이 의도적으로 .tracking 모드에서는 일반 Timer를 멈춥니다. 단, 스크롤과 무관한 작업(예: 네트워크 진행 표시)은 .common으로 등록하면 됩니다.

> 💡 **💡 면접 포인트:** "RunLoop은 메인 스레드의 이벤트 처리 엔진입니다. UIKit 앱에서 우리가 작성하는 거의 모든 콜백(touch, Timer, network completion, performSelector)이 RunLoop을 통해 전달됩니다. Timer + ScrollView 함정처럼 RunLoop 모드를 이해해야만 디버깅 가능한 이슈들이 있어요."


### 2. CADisplayLink와 60fps

_아이콘: `green`_


### CADisplayLink가 뭔가요?

"디스플레이 갱신 시점에 동기화된 콜백"입니다. Timer와 비슷하지만, 화면이 새로 그려지기 직전마다 정확히 호출됩니다.

### 왜 필요한가요?

일반 Timer는 시간 기반이라 화면 갱신과 어긋날 수 있습니다. 게임이나 부드러운 애니메이션엔 화면 갱신과 정확히 동기화되어야 자연스럽습니다.

### VSync와 프레임 예산

화면은 일정한 주기로 갱신됩니다. iPhone 기준:

| 디스플레이 | 주파수 | 프레임 시간 |
|---|---|---|
| 일반 디스플레이 | 60Hz | 16.67ms |
| ProMotion (iPhone 13 Pro+) | 120Hz | 8.33ms |

이 시간 안에 모든 처리(layout, draw, commit, GPU rendering)를 끝내야 부드럽게 보입니다. 초과하면 **프레임 드롭**이 발생합니다.

### 사용 예시

```swift
class GameView: UIView {
    var displayLink: CADisplayLink?
    
    func startAnimation() {
        displayLink = CADisplayLink(target: self, selector: #selector(update))
        
        // ProMotion 지원
        displayLink?.preferredFrameRateRange = CAFrameRateRange(
            minimum: 60, maximum: 120, preferred: 120
        )
        
        displayLink?.add(to: .main, forMode: .common)
    }
    
    @objc func update(_ link: CADisplayLink) {
        let elapsed = link.targetTimestamp - link.timestamp
        // elapsed가 16.67ms 초과 → 프레임 드롭!
        moveSprite(deltaTime: elapsed)
    }
    
    func stopAnimation() {
        displayLink?.invalidate()
        displayLink = nil
    }
}
```

### 렌더링 파이프라인

```swift
VSync 신호 → 다음 단계 진행:
1. CADisplayLink 콜백 호출
2. layoutSubviews() (레이아웃 계산)
3. draw(_:) (커스텀 드로잉)
4. CATransaction.commit (Render Server로 전송)
5. Render Server: GPU에 렌더링 명령
6. GPU 렌더링
7. 다음 VSync에 화면 표시

→ 16ms (또는 8ms) 안에 1~5 완료 필수!
```

> 💡 **💡 면접 포인트:** "ProMotion 지원 디바이스에서 120fps를 활용하려면 CADisplayLink의 preferredFrameRateRange를 명시해야 합니다. 미명시 시 기본값은 60fps로 제한됩니다. 또한 게임이나 애니메이션 외에는 일반 작업에 CADisplayLink를 쓰지 마세요 — 매 프레임마다 깨워서 배터리를 빨아먹습니다."


### 3. UI Layout Cycle (setNeedsLayout vs layoutIfNeeded)

_아이콘: `purple`_


### UIView의 레이아웃 동작

제약 조건이나 frame이 바뀌었다고 해서 즉시 다시 그려지진 않습니다. 시스템이 다음 RunLoop 사이클에 일괄 처리합니다.

### 3가지 핵심 메서드

### 1. setNeedsLayout()

"다음 사이클에 레이아웃 다시 계산해줘"라고 시스템에 부탁만 합니다. 즉시 실행되지 않습니다.

```swift
view.snp.updateConstraints { make in
    make.top.equalToSuperview().offset(100)
}
view.setNeedsLayout()  // 플래그만 설정
// 아직 layoutSubviews는 안 불림
```

### 2. layoutIfNeeded()

"지금 당장 레이아웃 해줘"라고 강제 실행합니다.

```swift
view.snp.updateConstraints { make in
    make.top.equalToSuperview().offset(100)
}
view.layoutIfNeeded()  // 즉시 layoutSubviews 호출
// 이 시점에 frame이 새 값으로 업데이트됨
```

### 3. layoutSubviews()

실제 레이아웃 계산이 일어나는 시스템 메서드. 직접 호출하면 안 됩니다.

### 애니메이션에서의 정석 패턴

```swift
// 제약 변경을 부드럽게 애니메이션:

// 1. 새 제약 적용
heightConstraint.constant = 200

// 2. UIView.animate 블록 안에서 layoutIfNeeded
UIView.animate(withDuration: 0.3) {
    self.view.layoutIfNeeded()  // 변경된 제약을 보간 애니메이션
}

// ❌ 이렇게 하면 애니메이션 안 됨
heightConstraint.constant = 200
UIView.animate(withDuration: 0.3) {
    // layoutIfNeeded 없으면 즉시 적용 vs 다음 사이클 적용 모호함
}
```

### setNeedsDisplay vs setNeedsLayout

| 메서드 | 트리거 | 용도 |
|---|---|---|
| `setNeedsLayout` | `layoutSubviews` | 서브뷰 위치/크기 재계산 |
| `setNeedsDisplay` | `draw(_:)` | 커스텀 드로잉 다시 그리기 |

### 왜 viewDidLoad에서 frame이 정확하지 않나요?

```swift
override func viewDidLoad() {
    super.viewDidLoad()
    print(view.bounds.width)  // ⚠️ 정확하지 않음!
    // viewDidLoad 시점엔 view가 아직 window에 추가되기 전
    // Auto Layout이 계산되지 않은 상태
}

override func viewDidLayoutSubviews() {
    super.viewDidLayoutSubviews()
    print(view.bounds.width)  // ✅ 이 시점부터 정확
    // 단, 여러 번 호출될 수 있으므로 일회성 작업은 주의
}
```

> 💡 **💡 면접 포인트:** "setNeedsLayout은 비동기 예약, layoutIfNeeded는 동기 강제 실행입니다. 애니메이션 블록에서 layoutIfNeeded를 호출하면 제약 변경이 보간 애니메이션으로 처리됩니다. viewDidLoad에서는 frame이 아직 확정되지 않았다는 점도 자주 묻는 함정이죠."


### 4. 왜 UI는 Main Thread에서만?

_아이콘: `orange`_


### "UIKit is not thread-safe" 라는 말의 의미

UIKit의 거의 모든 클래스는 thread-safe하지 않습니다. 즉, 여러 스레드에서 동시에 같은 UIKit 객체를 건드리면 데이터 손상, 크래시, 알 수 없는 버그가 발생할 수 있습니다.

### 왜 thread-safe하게 안 만들었나요?

**성능 때문입니다.** 모든 UI 호출에 lock을 걸면 매 작업마다 동기화 비용이 발생해서 60fps 유지가 어려워집니다. Apple은 "UI는 메인 스레드에서만 다룬다"는 규칙을 강제하는 대신 lock을 제거했습니다.

### 구체적으로 무엇이 일어나나요?

```swift
// 백그라운드 스레드에서 UI 변경 시도
DispatchQueue.global().async {
    self.label.text = "Hello"  // ⚠️ 위험!
    // 가능한 결과:
    // - 즉시 크래시
    // - 화면이 이상하게 그려짐
    // - 운 좋으면 동작 (가장 위험! 잠재 버그)
    // - 디버그 빌드에선 Thread Sanitizer가 잡아줌
}

// ✅ 항상 메인 스레드로 dispatch
DispatchQueue.global().async {
    let data = heavyTask()
    DispatchQueue.main.async {
        self.label.text = data  // 안전
    }
}

// 또는 Swift Concurrency:
Task {
    let data = await heavyTask()
    await MainActor.run {
        self.label.text = data
    }
}
```

### Render Server

iOS의 화면 렌더링은 별도 프로세스(`backboardd`)인 Render Server가 담당합니다. 앱은 layer 트리를 만들고 IPC로 전달만 합니다.

```swift
// 렌더링 파이프라인:
//
// [App Process]                [Render Server]      [GPU]
//  │                            │                    │
//  ├─ Layout                    │                    │
//  ├─ Display (draw)            │                    │
//  ├─ Prepare (이미지 디코딩)   │                    │
//  ├─ Commit (CA Transaction)   │                    │
//  │     ──IPC 전송──→         ├─ Layer tree        │
//  │                            ├─ 렌더링 명령        │
//  │                            │   ──전송──→        ├─ 합성
//  │                            │                    ├─ 표시
//
// 앱이 책임지는 부분: ~10ms 이내
// Render Server: ~5ms 이내
// 총 16ms 안에 끝나야 60fps
```

### Thread Sanitizer로 잡기

Xcode의 **Edit Scheme → Diagnostics → Thread Sanitizer** 켜면 백그라운드에서 UI 호출 시 즉시 경고가 뜹니다. 디버그 빌드에서 항상 켜두면 좋습니다.

> 💡 **💡 면접 포인트:** "UIKit이 thread-safe하지 않은 건 의도적 설계입니다. 모든 UI 호출에 lock을 걸면 60fps 유지가 어렵죠. 대신 \"UI는 메인 스레드\"라는 강력한 규칙을 두어 이 비용을 피합니다. Swift Concurrency에서는 @MainActor로 컴파일 타임에 이 규칙을 강제할 수 있어 더 안전해졌습니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. 스크롤 중에 Timer가 멈추는 이유는? `[기본 / 빈출]`

기본 `Timer.scheduledTimer`는 RunLoop의 `.default` 모드에 등록됩니다. 사용자가 스크롤을 시작하면 RunLoop이 `.tracking` 모드로 전환되고, `.default`에 등록된 Timer는 처리되지 않습니다.

**해결:**

```swift
RunLoop.main.add(timer, forMode: .common)
```
`.common`은 `.default`와 `.tracking`을 모두 포함하는 가상 모드라 항상 동작합니다.


### Q2. 왜 UI는 Main Thread에서만 업데이트해야 하나요? `[기본 / 빈출]`

세 가지 이유가 있습니다:

1. **UIKit이 thread-safe하지 않음**: 성능 이유로 lock 없이 설계됨. 멀티스레드 접근 시 데이터 손상 가능.
2. **Render Server 통신**: CA Transaction commit이 메인 스레드에서만 동작하도록 설계됨.
3. **이벤트 처리 순서**: touch → hit test → responder chain 모두 메인 스레드 RunLoop에서 처리됨.

Swift Concurrency의 @MainActor를 쓰면 컴파일 타임에 이 규칙을 강제할 수 있습니다.


### Q3. setNeedsLayout과 layoutIfNeeded의 차이는? `[기본 / 빈출]`

**setNeedsLayout()**: \"다음 RunLoop 사이클에 레이아웃을 다시 해줘\"라는 비동기 예약. 즉시 실행되지 않음.

**layoutIfNeeded()**: \"지금 당장 레이아웃 해줘\"라는 동기 실행. 변경된 제약이 즉시 반영됨.

**애니메이션 활용:**

```swift
heightConstraint.constant = 200\nUIView.animate(withDuration: 0.3) {\n    view.layoutIfNeeded()  // 보간 애니메이션\n}
```
제약 변경 후 layoutIfNeeded를 애니메이션 블록 안에서 호출하면 부드러운 전환 가능.


### Q4. viewDidLoad에서 view.frame이 정확하지 않은 이유는? `[심화 / 빈출]`

`viewDidLoad`는 view 계층이 로드된 직후 호출되지만, 이때는 view가 window에 추가되기 전입니다. Auto Layout 엔진이 아직 제약을 계산하지 않은 상태죠.

정확한 frame은 다음 시점부터 사용 가능합니다:
- `viewDidLayoutSubviews`: 레이아웃 완료 후 호출 (단, 여러 번 호출될 수 있음)
- `viewWillAppear` / `viewDidAppear`: 화면 표시 직전/직후

일회성 frame 기반 초기화는 `viewDidLayoutSubviews`에서 플래그를 두고 한 번만 실행하는 패턴을 사용합니다.


### Q5. DispatchQueue.main.async와 RunLoop.main.perform의 차이는? `[심화]`

**DispatchQueue.main.async**: GCD 통해 메인 큐에 enqueue. 다음 RunLoop 사이클에 처리.

**RunLoop.main.perform**: RunLoop의 Source 0에 직접 등록. 모드 지정 가능 (예: scrolling 중에도 동작하게).

대부분의 경우 동일하게 동작하지만, 미묘한 차이가 있을 수 있습니다. RunLoop.main.perform은 특정 RunLoop 모드에서만 실행되도록 제어 가능하다는 장점이 있어요.


---


## ✏️ 퀴즈


### 문제 1

RunLoop.common 모드에 Timer를 추가하는 이유는?


   **A.** Timer의 정확도를 높이기 위해

✅ **B.** 스크롤 중에도 Timer가 동작하도록 하기 위해

   **C.** Timer의 메모리 사용량을 줄이기 위해

   **D.** 백그라운드에서도 Timer가 동작하도록 하기 위해


**정답**: B


💡 **힌트**: .common은 .default와 .tracking을 모두 포함하는 가상 mode입니다.


### 문제 2

60Hz 디스플레이에서 한 프레임당 예산은?


   **A.** 8.33ms

✅ **B.** 16.67ms

   **C.** 33.33ms

   **D.** 60ms


**정답**: B


💡 **힌트**: 1초(1000ms) ÷ 60 = ?


### 문제 3

setNeedsLayout만 호출하고 layoutIfNeeded는 호출하지 않으면?


   **A.** 즉시 layoutSubviews가 호출된다

✅ **B.** 다음 RunLoop 사이클에 layoutSubviews가 호출된다

   **C.** layoutSubviews가 영원히 호출되지 않는다

   **D.** 컴파일 에러가 발생한다


**정답**: B


💡 **힌트**: setNeedsLayout은 비동기 예약입니다.


