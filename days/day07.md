# Day 7 — App Lifecycle와 Scene 기반 구조

**태그**: UIScene · UIApplicationDelegate · Background · State Restoration · BGTask

---

## 📝 핵심 정리


### 1. App과 Scene Lifecycle

_아이콘: `blue`_


### iOS 13에서 바뀐 것

iOS 13 이전: `UIApplicationDelegate`가 모든 lifecycle 관리.
iOS 13 이후: `UISceneDelegate`가 UI lifecycle 담당. AppDelegate는 앱 전역 설정만.

### 왜 분리했나요?

iPad의 멀티 윈도우 지원 때문입니다. 한 앱이 여러 창을 가질 수 있게 되면서, 각 창(Scene)이 독립적인 lifecycle을 가져야 했습니다.

### 앱 상태 (Application State)

```swift
// 앱 전체 상태:
Not Running → Inactive → Active → Background → Suspended → Terminated
                              ↕
                        Inactive

// 각 상태 의미:
// Not Running: 실행 안 됨
// Inactive: 포그라운드지만 이벤트 못 받음 (전화 수신 등)
// Active: 정상 동작 중
// Background: 백그라운드 실행 중 (제한된 시간)
// Suspended: 백그라운드에서 실행 멈춤 (메모리만 점유)
// Terminated: 종료됨
```

### Scene 상태

```swift
// 각 윈도우의 상태:
Unattached → Foreground Inactive → Foreground Active
                                ↕
                           Background → Suspended → 시스템이 메모리 회수 시 제거
```

### 앱 시작 시 콜백 순서

```swift
// 1. AppDelegate 메서드:
func application(_ app: UIApplication,
                 didFinishLaunchingWithOptions: ...) -> Bool {
    // 앱 전역 초기화 (최소한만!)
    // 너무 오래 걸리면 watchdog이 앱 강제 종료
    return true
}

// 2. SceneDelegate 메서드들:
func scene(_ scene: UIScene,
           willConnectTo session: UISceneSession,
           options: UIScene.ConnectionOptions) {
    // UI 설정, 첫 화면 구성
}

func sceneWillEnterForeground(_ scene: UIScene) {
    // 포그라운드 진입 준비
}

func sceneDidBecomeActive(_ scene: UIScene) {
    // 활성화 완료, 사용자 입력 받을 준비
}
```

### 백그라운드 진입 콜백 (가장 중요!)

```swift
func sceneWillResignActive(_ scene: UIScene) {
    // 비활성화 시작 (전화, 알림 센터 등)
    // 게임이라면 일시정지
}

func sceneDidEnterBackground(_ scene: UIScene) {
    // ⚠️ 5초 이내에 작업 완료해야 함!
    // 이 시점에 앱 스위처용 스냅샷 촬영됨
    
    // 해야 할 일:
    saveContext()           // Core Data 저장
    archiveUserDefaults()   // 설정 저장
    invalidateTimers()      // 리소스 정리
    
    // 더 긴 작업 필요하면 BGTaskScheduler 사용
}
```

> 💡 **💡 면접 포인트:** "iOS 13+ 멀티 윈도우 지원 시 SceneDelegate 기반으로 전환해야 합니다. AppDelegate는 앱 전역 설정(Firebase 초기화 등), SceneDelegate는 UI 상태 관리(네비게이션 스택 등)로 책임을 분리하는 게 깔끔합니다."


### 2. Background Execution

_아이콘: `green`_


### 백그라운드에서 코드 실행하기

iOS는 배터리 보호를 위해 백그라운드 실행을 엄격히 제한합니다. 두 가지 방법이 있습니다.

### 1. UIBackgroundTask (짧은 작업, ~30초)

"앱이 백그라운드로 가도 이 작업은 마저 끝낼게요"라고 시스템에 요청합니다.

```swift
func sceneDidEnterBackground(_ scene: UIScene) {
    var bgTask: UIBackgroundTaskIdentifier = .invalid
    
    bgTask = UIApplication.shared.beginBackgroundTask {
        // 시간 초과 시 호출됨
        UIApplication.shared.endBackgroundTask(bgTask)
        bgTask = .invalid
    }
    
    DispatchQueue.global().async {
        // 백그라운드에서 작업 수행
        self.uploadPendingData()
        
        // 작업 완료 시 반드시 endBackgroundTask 호출!
        UIApplication.shared.endBackgroundTask(bgTask)
        bgTask = .invalid
    }
}
```

최대 ~30초 정도 보장됩니다. 종료 시점은 시스템이 결정합니다.

### 2. BGTaskScheduler (iOS 13+, 긴 작업)

"가끔 앱을 깨워서 백그라운드 작업을 시켜주세요"라고 시스템에 등록합니다.

```swift
// Info.plist에 BGTaskSchedulerPermittedIdentifiers 등록 필요
// "com.app.refresh" 같은 식별자

// AppDelegate에서 등록:
BGTaskScheduler.shared.register(
    forTaskWithIdentifier: "com.app.refresh",
    using: nil
) { task in
    handleRefresh(task: task as! BGAppRefreshTask)
}

// 다음 실행 예약
func scheduleAppRefresh() {
    let request = BGAppRefreshTaskRequest(identifier: "com.app.refresh")
    request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)  // 15분 후
    try? BGTaskScheduler.shared.submit(request)
}

// 실제 처리
func handleRefresh(task: BGAppRefreshTask) {
    scheduleAppRefresh()  // 다음 실행 예약 (안 하면 더 이상 안 깨움!)
    
    let operation = RefreshOperation()
    
    task.expirationHandler = {
        operation.cancel()  // 시간 초과 시 취소
    }
    
    operation.completionBlock = {
        task.setTaskCompleted(success: !operation.isCancelled)
    }
    
    operationQueue.addOperation(operation)
}
```

BGTaskScheduler는 시스템이 "지금 깨우는 게 좋겠다"는 시점에 호출합니다. 정확한 시간 보장은 없습니다.

### 다른 백그라운드 모드

| 모드 | 용도 |
|---|---|
| Audio | 음악 재생 앱 |
| Location | 내비, 운동 추적 |
| VoIP | 전화 앱 |
| Background fetch | 콘텐츠 미리 가져오기 |
| Remote notifications | silent push로 깨우기 |
| Background processing | 긴 처리 (BGProcessingTask) |

> 💡 **💡 면접 포인트:** "iOS 백그라운드 실행은 배터리 보호를 위해 매우 제한적입니다. UIBackgroundTask는 즉각적인 짧은 마무리(~30초), BGTaskScheduler는 가끔 시스템이 깨워주는 정기 작업입니다. 정확한 타이밍이 필요하면 silent push를 활용하는 패턴도 있어요."


### 3. 앱이 종료되는 다양한 시점

_아이콘: `purple`_


### 앱이 종료되는 5가지 경우

- **사용자가 명시적으로 종료**: 앱 스위처에서 위로 스와이프

- **메모리 부족 (Jetsam)**: 시스템이 백그라운드 앱을 죽임

- **크래시**: 예외 발생

- **Watchdog 타임아웃**: didFinishLaunching이 너무 오래 걸림

- **앱 업데이트**: 새 버전 설치 시

### 각 경우의 콜백

| 종료 시점 | applicationWillTerminate |
|---|---|
| 사용자 강제 종료 | 호출 안 됨! |
| 백그라운드에서 시스템 종료 | 호출됨 (Background 상태일 때만) |
| Suspended에서 메모리 회수 | 호출 안 됨! |
| 크래시 | 호출 안 됨 |

**핵심: applicationWillTerminate를 절대 믿지 마세요.** 중요한 데이터는 sceneDidEnterBackground에서 저장해야 합니다.

### didReceiveMemoryWarning

```swift
// 시스템 메모리 압박 시 포그라운드 앱에 전달
override func didReceiveMemoryWarning() {
    super.didReceiveMemoryWarning()
    
    // 캐시 정리
    imageCache.removeAllObjects()
    
    // 사용 안 하는 리소스 해제
    if !isViewLoaded || view.window == nil {
        view = nil
    }
}

// 이 경고를 무시하면 시스템이 앱을 강제 종료!
```

### State Restoration (상태 복원)

앱이 시스템에 의해 종료된 후 다시 시작될 때, 사용자가 보던 화면으로 복원해주는 기능입니다.

```swift
// SceneDelegate
func stateRestorationActivity(for scene: UIScene) -> NSUserActivity? {
    // 앱 종료 직전 호출 → 상태 저장
    let activity = NSUserActivity(activityType: "com.app.viewing")
    activity.userInfo = [
        "selectedTab": tabIndex,
        "scrollY": scrollOffset,
        "detailItemID": currentItemID ?? ""
    ]
    return activity
}

func scene(_ scene: UIScene,
           willConnectTo session: UISceneSession,
           options: UIScene.ConnectionOptions) {
    if let activity = session.stateRestorationActivity {
        // 저장된 상태로 복원
        let tab = activity.userInfo?["selectedTab"] as? Int ?? 0
        let scrollY = activity.userInfo?["scrollY"] as? CGFloat ?? 0
        // ... 복원 로직
    }
}

// 주의:
// - 사용자가 명시적으로 종료(스와이프 킬)하면 복원 안 됨
// - 민감 화면(비밀번호 입력 등)은 복원 안 하는 게 좋음
```

> 💡 **💡 면접 포인트:** "applicationWillTerminate에 의존하면 안 됩니다. 사용자 강제 종료, Suspended에서의 시스템 종료에는 호출되지 않거든요. 중요한 데이터는 항상 백그라운드 진입 시점(sceneDidEnterBackground)에 저장해야 안전합니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. 앱이 메모리 부족으로 종료될 때 어떤 콜백이 호출되나요? `[심화 / 빈출]`

**아무것도 호출되지 않습니다.**

Suspended 상태에서 시스템(Jetsam)이 조용히 프로세스를 종료시킵니다. `applicationWillTerminate`도, `sceneDidEnterBackground`도 다시 호출되지 않습니다.

그래서 중요한 데이터는 백그라운드 진입 시점(`sceneDidEnterBackground`)에 모두 저장해두어야 합니다. `applicationWillTerminate`는 백그라운드 상태에서 시스템이 정상 종료할 때만 호출되며, 신뢰할 수 없습니다.


### Q2. didReceiveMemoryWarning은 언제 오나요? `[기본 / 빈출]`

시스템 전체 메모리가 부족할 때 포그라운드 앱에 전달됩니다.

여기서 해야 할 일:
- 이미지/데이터 캐시 정리
- 보이지 않는 ViewController의 무거운 리소스 해제
- 재계산 가능한 데이터 버리기

이 경고를 무시하면 시스템이 앱을 강제 종료할 수 있습니다. 또한 여러 번 무시하면 시스템이 \"이 앱은 메모리를 안 줄이네\" 학습해서 더 빨리 죽일 수도 있어요.


### Q3. AppDelegate와 SceneDelegate는 어떻게 책임을 나누나요? `[기본 / 빈출]`

**AppDelegate:** 앱 전역 설정. 한 번만 실행되는 것들.
- Firebase, Crashlytics 초기화
- 푸시 알림 권한
- 앱 전역 상태 (로그인 등)
- BGTaskScheduler 등록

**SceneDelegate:** 윈도우(Scene) 단위 UI 상태.
- 첫 화면 구성
- 네비게이션 스택
- 활성/비활성 전환 처리
- 상태 복원

iPad 멀티 윈도우에서 각 Scene이 독립적인 UI를 가지므로 분리가 의미 있습니다.


### Q4. BGTaskScheduler를 사용하는 이유는? `[기본]`

앱이 백그라운드/종료된 상태에서도 가끔 작업을 수행해야 할 때 사용합니다. 예: 배경 동기화, 정기적 데이터 갱신.

특징:
- 시스템이 \"지금 깨우면 좋겠다\"는 시점에 호출 (정확한 시간 보장 X)
- 배터리, 네트워크 상태 등을 고려해 시스템이 결정
- handleAppRefresh에서 다음 실행을 다시 예약해야 계속 깨움
- expirationHandler에서 작업 취소 처리 필수

UIBackgroundTask와 차이: BG는 단발성 마무리, BGTaskScheduler는 정기적 깨움.


---


## ✏️ 퀴즈


### 문제 1

applicationWillTerminate가 호출되는 경우는?


   **A.** 사용자가 앱 스위처에서 위로 스와이프할 때

   **B.** 앱이 메모리 부족으로 백그라운드에서 종료될 때

✅ **C.** 앱이 백그라운드 상태에서 시스템에 의해 정상 종료될 때

   **D.** 앱이 크래시할 때


**정답**: C


💡 **힌트**: Suspended에서의 종료, 강제 종료, 크래시 모두 호출되지 않습니다.


### 문제 2

Scene이 백그라운드로 진입할 때 작업 완료 시간은 얼마인가요?


   **A.** 1초

✅ **B.** 5초

   **C.** 30초

   **D.** 제한 없음


**정답**: B


💡 **힌트**: sceneDidEnterBackground 직후 약 5초의 짧은 시간 안에 작업을 마쳐야 합니다.


