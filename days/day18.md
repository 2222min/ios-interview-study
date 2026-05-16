# Day 18 — Instruments 프로파일링

**태그**: Time Profiler · Allocations · Leaks · Core Animation · MetricKit

---

## 📝 핵심 정리


### 1. Time Profiler & Allocations

_아이콘: `blue`_


### Time Profiler

CPU 사용량을 시간 기반으로 샘플링하여 **어떤 함수가 CPU 시간을 많이 소비하는지** 분석합니다. 1ms마다 콜 스택을 캡처합니다.

### Time Profiler 사용법

```swift
// Xcode → Product → Profile (⌘I) → Time Profiler 선택

// 핵심 설정:
// 1. "Separate by Thread" 체크 → 메인 스레드 병목 확인
// 2. "Invert Call Tree" 체크 → 가장 비용 큰 함수부터 표시
// 3. "Hide System Libraries" 체크 → 내 코드만 표시

// 분석 포인트:
// - Main Thread에서 오래 걸리는 작업 → 프레임 드롭 원인
// - Weight(%)가 높은 함수 → 최적화 대상
// - 반복 호출되는 함수 → 캐싱 고려
```

### Allocations

메모리 할당/해제를 추적합니다. **메모리 증가 추세와 누수**를 파악합니다.

```swift
// Allocations 분석 방법:
//
// 1. "Mark Generation" 버튼으로 스냅샷 찍기
//    - 화면 진입 전 Mark → 화면 진입 → 화면 나감 → Mark
//    - 두 Mark 사이에 남아있는 객체 = 잠재적 누수
//
// 2. "All Heap Allocations" 필터링
//    - 내 클래스명으로 검색
//    - Persistent(해제 안 된) 객체 확인
//
// 3. Growth 확인
//    - 같은 동작 반복 시 메모리가 계속 증가하면 누수

// 코드에서 메모리 추적
import os

let signpostLog = OSLog(subsystem: "com.myapp", category: "Performance")

func processData() {
    os_signpost(.begin, log: signpostLog, name: "DataProcessing")
    // ... 작업
    os_signpost(.end, log: signpostLog, name: "DataProcessing")
}
```

### Leaks Instrument

```swift
// Leaks: 순환 참조로 인한 메모리 누수 자동 탐지
//
// 동작 원리:
// 1. 힙의 모든 객체를 스캔
// 2. 루트(스택, 전역변수)에서 도달 불가능한 객체 탐지
// 3. 해당 객체의 retain cycle 그래프 표시
//
// 실무 팁:
// - 화면 push/pop을 반복하며 Leaks 확인
// - 보라색 X 표시 = 누수 발견
// - Cycles & Roots 탭에서 순환 참조 경로 확인

// 디버그 빌드에서 누수 감지 자동화
class LeakDetector {
    static func detect(_ object: AnyObject, file: String = #file) {
        let weak = Weak(object: object)
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
            if weak.object != nil {
                print("⚠️ 잠재적 누수: \\(type(of: object)) in \\(file)")
            }
        }
    }
}

private class Weak {
    weak var object: AnyObject?
    init(object: AnyObject) { self.object = object }
}
```

> 💡 **💡 면접 포인트:** "Time Profiler로 CPU 병목을 찾고, Allocations로 메모리 증가 추세를 확인합니다. Leaks는 순환 참조를 자동 탐지합니다. 실무에서는 화면 전환을 반복하며 Mark Generation으로 메모리 누수를 체계적으로 검증합니다."


### 2. Core Animation 디버깅

_아이콘: `green`_


### Core Animation Instrument

UI 렌더링 성능을 분석합니다. **60fps(16.67ms/frame)**를 유지하지 못하는 원인을 찾습니다.

### 주요 디버깅 옵션

```swift
// Simulator → Debug 메뉴 또는 Instruments → Core Animation

// 1. Color Blended Layers (빨간색 = 블렌딩 발생)
//    - 투명 뷰가 겹치면 GPU가 블렌딩 계산
//    - 해결: backgroundColor 설정, isOpaque = true

// 2. Color Offscreen-Rendered (노란색 = 오프스크린 렌더링)
//    - cornerRadius + clipsToBounds 조합
//    - shadow 없이 shadowPath 미설정
//    - 해결: layer.shouldRasterize = true 또는 미리 그린 이미지 사용

// 3. Color Hits Green and Misses Red
//    - shouldRasterize 캐시 히트/미스 확인
//    - 빨간색이 많으면 캐시가 무효화되고 있음

// 4. Color Copied Images (파란색 = 이미지 복사)
//    - GPU가 처리할 수 없는 포맷의 이미지
//    - 해결: 적절한 포맷으로 미리 변환
```

### 오프스크린 렌더링 최적화

```swift
// ❌ 오프스크린 렌더링 유발
imageView.layer.cornerRadius = 10
imageView.clipsToBounds = true  // 오프스크린!

// ✅ 해결 1: CALayer의 maskedCorners 사용 (iOS 11+)
imageView.layer.cornerRadius = 10
imageView.layer.maskedCorners = [.layerMinXMinYCorner, .layerMaxXMinYCorner]
// clipsToBounds 없이도 동작

// ✅ 해결 2: 미리 둥근 이미지 생성
func roundedImage(_ image: UIImage, radius: CGFloat) -> UIImage {
    let renderer = UIGraphicsImageRenderer(size: image.size)
    return renderer.image { context in
        let rect = CGRect(origin: .zero, size: image.size)
        UIBezierPath(roundedRect: rect, cornerRadius: radius).addClip()
        image.draw(in: rect)
    }
}

// ❌ Shadow 오프스크린 렌더링
view.layer.shadowColor = UIColor.black.cgColor
view.layer.shadowOffset = CGSize(width: 0, height: 2)
view.layer.shadowOpacity = 0.3
// shadowPath 없으면 매 프레임 계산!

// ✅ shadowPath 지정
view.layer.shadowPath = UIBezierPath(
    roundedRect: view.bounds,
    cornerRadius: view.layer.cornerRadius
).cgPath
```

### 프레임 드롭 원인 Top 5

- 메인 스레드에서 이미지 디코딩

- 오프스크린 렌더링 (cornerRadius + clipsToBounds)

- 투명 뷰 과다 블렌딩

- Auto Layout 복잡도 (중첩 스택뷰)

- 셀 높이 계산 반복 (UITableView)

> 💡 **💡 면접 답변:** "Core Animation 디버깅에서 Color Blended Layers로 불필요한 투명도를, Color Offscreen-Rendered로 오프스크린 렌더링을 확인합니다. cornerRadius는 clipsToBounds 대신 maskedCorners를 사용하고, shadow는 반드시 shadowPath를 지정하여 GPU 부하를 줄입니다."


### 3. MetricKit으로 실사용자 성능 수집

_아이콘: `purple`_


### MetricKit이란?

iOS 13+에서 **실제 사용자 기기의 성능 데이터를 수집**하는 프레임워크입니다. 24시간 단위로 집계된 메트릭을 앱에 전달합니다.

### MetricKit 설정

```swift
import MetricKit

class MetricsManager: NSObject, MXMetricManagerSubscriber {
    
    static let shared = MetricsManager()
    
    func setup() {
        MXMetricManager.shared.add(self)
    }
    
    // 24시간마다 호출 (iOS 14+에서는 즉시 진단도 가능)
    func didReceive(_ payloads: [MXMetricPayload]) {
        for payload in payloads {
            // 앱 실행 시간
            if let launchMetrics = payload.applicationLaunchMetrics {
                let resumeTime = launchMetrics.histogrammedResumeTime
                let optimizedTime = launchMetrics.histogrammedOptimizedTimeToFirstDraw
                reportToServer(launch: optimizedTime)
            }
            
            // 메모리
            if let memoryMetrics = payload.memoryMetrics {
                let peakMemory = memoryMetrics.peakMemoryUsage
                reportToServer(memory: peakMemory)
            }
            
            // CPU
            if let cpuMetrics = payload.cpuMetrics {
                let cpuTime = cpuMetrics.cumulativeCPUTime
                reportToServer(cpu: cpuTime)
            }
            
            // 디스크 I/O
            if let diskMetrics = payload.diskIOMetrics {
                let writes = diskMetrics.cumulativeLogicalWrites
                reportToServer(disk: writes)
            }
        }
    }
    
    // iOS 14+: 크래시/행 진단
    func didReceive(_ payloads: [MXDiagnosticPayload]) {
        for payload in payloads {
            // 크래시 리포트
            if let crashDiagnostics = payload.crashDiagnostics {
                for crash in crashDiagnostics {
                    let callStack = crash.callStackTree
                    reportCrash(callStack)
                }
            }
            
            // 행(Hang) 진단 - 메인 스레드 블록
            if let hangDiagnostics = payload.hangDiagnostics {
                for hang in hangDiagnostics {
                    let duration = hang.hangDuration
                    reportHang(duration: duration, stack: hang.callStackTree)
                }
            }
        }
    }
}
```

### 수집 가능한 메트릭

| 카테고리 | 메트릭 |
|---|---|
| Launch | Time to First Draw, Resume Time |
| Memory | Peak Memory, Suspended Memory |
| CPU | CPU Time, CPU Instructions |
| Disk | Logical Writes |
| Network | Transfer Bytes, Cellular Upload/Download |
| Animation | Scroll Hitch Rate (iOS 15+) |

> 💡 **💡 면접 답변:** "MetricKit은 실제 사용자 환경의 성능 데이터를 수집합니다. Instruments는 개발 환경에서의 프로파일링이고, MetricKit은 프로덕션 모니터링입니다. iOS 15+의 Scroll Hitch Rate로 실사용자의 스크롤 끊김을 정량적으로 측정할 수 있습니다. 이 데이터를 서버로 전송하여 성능 대시보드를 구축합니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. Time Profiler에서 Invert Call Tree의 의미는? `[기본 / 빈출]`

**콜 스택을 뒤집어서 가장 비용이 큰 '말단 함수'부터 보여줍니다.**

기본 모드는 main() → AppDelegate → ViewController → ... 순서로 위에서 아래로 보여줍니다. Invert하면 실제로 CPU를 소비한 함수가 맨 위에 오므로 병목을 빠르게 찾을 수 있습니다.

예: JSONDecoder.decode()가 40% → 이 함수를 최적화하거나 백그라운드로 이동


### Q2. 오프스크린 렌더링이 성능에 미치는 영향은? `[기본 / 빈출]`

**GPU가 별도 버퍼를 할당하여 렌더링 후 다시 합성하는 추가 작업이 발생합니다.**

일반 렌더링: GPU가 프레임버퍼에 직접 그림
오프스크린: 별도 버퍼 할당 → 그리기 → 원래 버퍼에 합성 (context switch 2번)

스크롤 중 셀마다 오프스크린이 발생하면 16ms를 초과하여 프레임 드롭이 생깁니다. cornerRadius, shadow, mask, group opacity가 주요 원인입니다.


### Q3. MetricKit과 Instruments의 차이는? `[심화 / 빈출]`

**측정 환경이 다릅니다.**

• **Instruments**: 개발 환경에서 디버그 빌드를 프로파일링. 상세한 콜 스택과 타임라인 제공. 문제 원인 분석에 적합
• **MetricKit**: 프로덕션 환경에서 릴리즈 빌드의 실사용자 데이터 수집. 24시간 집계. 실제 성능 모니터링에 적합

둘을 함께 사용: MetricKit으로 문제를 감지하고, Instruments로 원인을 분석합니다.


---


## ✏️ 퀴즈


### 문제 1

Instruments에서 메모리 누수를 탐지하는 도구는?


   **A.** Time Profiler

   **B.** Allocations의 Mark Generation

✅ **C.** Leaks

   **D.** Core Animation


**정답**: C


💡 **힌트**: 순환 참조로 인해 해제되지 않는 객체를 자동으로 탐지합니다.


### 문제 2

오프스크린 렌더링을 유발하지 않는 것은?


   **A.** cornerRadius + clipsToBounds

   **B.** shadowPath 없는 shadow

   **C.** layer.mask 사용

✅ **D.** backgroundColor 설정


**정답**: D


💡 **힌트**: 불투명한 배경색 설정은 오히려 블렌딩을 줄여 성능을 향상시킵니다.


