# Day 20 — System Design & 면접 전략

**태그**: Feed App · Chat App · STAR-T · System Design · Follow-up Questions

---

## 📝 핵심 정리


### 1. Feed App 시스템 설계

_아이콘: `blue`_


### 면접에서 Feed App 설계 질문

"인스타그램/트위터 같은 피드 앱의 iOS 클라이언트를 설계해주세요"는 시니어 면접의 단골 질문입니다.

### 설계 프레임워크 (4단계)

```swift
// 1단계: 요구사항 명확화 (2분)
// - 피드 타입: 텍스트? 이미지? 비디오?
// - 페이지네이션: 무한 스크롤? Pull-to-refresh?
// - 오프라인 지원 필요?
// - 실시간 업데이트?

// 2단계: 고수준 아키텍처 (5분)
//
// ┌─────────────────────────────────────────┐
// │              Presentation               │
// │  FeedViewController ← FeedViewModel     │
// ├─────────────────────────────────────────┤
// │              Domain                     │
// │  FeedUseCase ← FeedRepository(Protocol) │
// ├─────────────────────────────────────────┤
// │              Data                       │
// │  FeedRepositoryImpl                     │
// │  ├─ RemoteDataSource (API)              │
// │  ├─ LocalDataSource (Core Data)         │
// │  └─ CachePolicy                        │
// ├─────────────────────────────────────────┤
// │              Infrastructure             │
// │  NetworkService, ImageCache, Analytics  │
// └─────────────────────────────────────────┘
```

### 3단계: 핵심 컴포넌트 상세 (10분)

```swift
// 페이지네이션
class FeedViewModel: ObservableObject {
    @Published var posts: [Post] = []
    @Published var isLoading = false
    private var cursor: String?
    private var hasMore = true
    
    func loadNextPage() async {
        guard !isLoading, hasMore else { return }
        isLoading = true
        
        let result = await feedUseCase.fetchFeed(cursor: cursor, limit: 20)
        switch result {
        case .success(let response):
            posts.append(contentsOf: response.posts)
            cursor = response.nextCursor
            hasMore = response.hasMore
        case .failure(let error):
            handleError(error)
        }
        isLoading = false
    }
}

// 이미지 로딩 전략
// - 썸네일: 즉시 로드 (작은 크기)
// - 원본: 탭 시 로드
// - Prefetch: 다음 5개 셀 미리 로드
// - 캐시: Memory → Disk → Network

// 오프라인 지원
class CachePolicy {
    func shouldFetchFromNetwork(lastSync: Date?) -> Bool {
        guard let lastSync = lastSync else { return true }
        return Date().timeIntervalSince(lastSync) > 300  // 5분
    }
    
    func fetchFeed() async -> [Post] {
        if shouldFetchFromNetwork(lastSync: lastSyncDate) {
            let posts = try await remoteDataSource.fetch()
            localDataSource.save(posts)
            return posts
        }
        return localDataSource.fetch()
    }
}
```

### 4단계: 트레이드오프 논의 (3분)

- **Cursor vs Offset 페이지네이션**: Cursor가 실시간 피드에 적합 (중간 삽입/삭제에 안전)

- **Pull vs Push 업데이트**: WebSocket은 배터리 소모, Polling은 지연. 하이브리드 권장

- **캐시 무효화**: TTL 기반 vs 서버 Push 기반

> 💡 **💡 면접 포인트:** "시스템 설계 질문에서는 바로 코드를 쓰지 말고, 요구사항 명확화 → 고수준 설계 → 상세 설계 → 트레이드오프 순서로 진행합니다. 면접관이 원하는 건 '정답'이 아니라 '사고 과정'입니다."


### 2. Chat App 시스템 설계

_아이콘: `green`_


### 실시간 채팅 앱 iOS 클라이언트 설계

### 핵심 도전 과제

- 실시간 메시지 송수신

- 오프라인 메시지 큐잉

- 메시지 순서 보장

- 읽음 확인

- 미디어 전송

### 아키텍처

```swift
// 실시간 통신 레이어
class WebSocketManager {
    private var socket: URLSessionWebSocketTask?
    private let messageSubject = PassthroughSubject<ChatMessage, Never>()
    
    var messages: AnyPublisher<ChatMessage, Never> {
        messageSubject.eraseToAnyPublisher()
    }
    
    func connect() {
        let url = URL(string: "wss://chat.example.com/ws")!
        socket = URLSession.shared.webSocketTask(with: url)
        socket?.resume()
        receiveMessage()
    }
    
    private func receiveMessage() {
        socket?.receive { [weak self] result in
            switch result {
            case .success(.string(let text)):
                if let message = try? JSONDecoder().decode(ChatMessage.self, from: Data(text.utf8)) {
                    self?.messageSubject.send(message)
                }
            default: break
            }
            self?.receiveMessage()  // 계속 수신 대기
        }
    }
    
    func send(_ message: ChatMessage) {
        let data = try? JSONEncoder().encode(message)
        socket?.send(.string(String(data: data!, encoding: .utf8)!)) { error in
            if let error = error {
                // 오프라인 큐에 저장
                OfflineQueue.shared.enqueue(message)
            }
        }
    }
}

// 메시지 상태 관리
enum MessageStatus {
    case sending    // 전송 중 (로컬)
    case sent       // 서버 도달
    case delivered  // 상대방 기기 도달
    case read       // 상대방 읽음
    case failed     // 전송 실패
}

// 오프라인 큐
class OfflineQueue {
    static let shared = OfflineQueue()
    private var queue: [ChatMessage] = []
    
    func enqueue(_ message: ChatMessage) {
        queue.append(message)
        persistToDisk()
    }
    
    func flush() async {
        for message in queue {
            try? await sendToServer(message)
        }
        queue.removeAll()
    }
}
```

### 메시지 순서 보장

```swift
// 서버 타임스탬프 + 로컬 시퀀스 번호
struct ChatMessage: Codable {
    let id: String           // UUID
    let localSeq: Int        // 로컬 순서 (낙관적 표시용)
    let serverTimestamp: Date?  // 서버 확정 순서
    let content: String
    let status: MessageStatus
}

// UI에서는 serverTimestamp 기준 정렬
// serverTimestamp가 nil이면 (아직 서버 미도달) localSeq로 임시 정렬
```

> 💡 **💡 면접 답변:** "채팅 앱의 핵심은 실시간성과 신뢰성의 균형입니다. WebSocket으로 실시간 통신하되, 연결 끊김 시 오프라인 큐에 저장하고 재연결 시 flush합니다. 메시지 순서는 서버 타임스탬프로 확정하고, 낙관적 UI로 사용자 경험을 유지합니다."


### 3. STAR-T 답변 프레임워크

_아이콘: `orange`_


### STAR-T란?

행동 면접(Behavioral Interview) 질문에 구조적으로 답변하는 프레임워크입니다. 기술 면접에서도 경험 기반 질문에 활용합니다.

### 구조

```swift
// S - Situation (상황): 배경 설명 (1~2문장)
// T - Task (과제): 내가 해결해야 했던 문제 (1문장)
// A - Action (행동): 내가 취한 구체적 행동 (2~3문장)
// R - Result (결과): 정량적 결과 (숫자로!)
// T - Takeaway (교훈): 배운 점, 다음에 다르게 할 것
```

### 예시 1: 성능 최적화 경험

```swift
// Q: "성능 문제를 해결한 경험을 말씀해주세요"

// S: "커머스 앱의 상품 목록 화면에서 스크롤 시 
//     심한 프레임 드롭이 발생했습니다."

// T: "60fps를 유지하면서 이미지가 많은 목록을 
//     부드럽게 스크롤할 수 있도록 최적화해야 했습니다."

// A: "Instruments Time Profiler로 분석한 결과, 
//     메인 스레드에서 이미지 디코딩이 병목이었습니다.
//     ImageIO 기반 downsampling을 도입하고,
//     prefetching으로 미리 디코딩하도록 변경했습니다.
//     또한 셀의 cornerRadius를 CAShapeLayer로 교체하여
//     오프스크린 렌더링을 제거했습니다."

// R: "평균 프레임 레이트가 38fps에서 58fps로 개선되었고,
//     메모리 사용량이 380MB에서 120MB로 68% 감소했습니다.
//     사용자 이탈률이 12% 감소했습니다."

// T: "성능 문제는 측정 먼저, 최적화는 나중이라는 원칙을 
//     다시 확인했습니다. 이후 MetricKit을 도입하여 
//     프로덕션 성능을 상시 모니터링하고 있습니다."
```

### 예시 2: 아키텍처 결정

```swift
// Q: "기술적으로 어려운 결정을 내린 경험은?"

// S: "5명이 동시 개발하는 앱에서 빌드 시간이 8분을 넘어
//     개발 생산성이 크게 저하되었습니다."

// T: "빌드 시간을 3분 이내로 줄이면서 
//     팀원들의 학습 비용을 최소화해야 했습니다."

// A: "Tuist를 도입하여 모듈화를 진행했습니다.
//     Feature/Domain/Core 3계층으로 분리하고,
//     Interface 모듈 패턴으로 빌드 캐시를 극대화했습니다.
//     팀 세미나와 템플릿을 제공하여 학습 비용을 줄였습니다."

// R: "클린 빌드 8분 → 3분, 증분 빌드 2분 → 20초.
//     PR 머지 충돌이 주 15건에서 3건으로 감소.
//     팀 만족도 조사에서 개발 환경 점수 4.2/5.0."

// T: "도구 도입보다 팀의 합의와 교육이 더 중요하다는 걸 
//     배웠습니다. 기술 결정은 항상 팀과 함께 해야 합니다."
```

### 흔한 Follow-up 질문과 대응

| 질문 | 의도 | 대응 전략 |
|---|---|---|
| "다시 한다면 다르게 할 것은?" | 성장 마인드셋 | 구체적 개선점 + 이유 |
| "팀원이 반대했다면?" | 협업 능력 | 데이터 기반 설득 + 타협점 |
| "스케일이 10배라면?" | 확장성 사고 | 현재 한계 인정 + 대안 제시 |
| "측정은 어떻게?" | 데이터 중심 | 구체적 도구와 메트릭 언급 |

> 💡 **💡 핵심:** STAR-T에서 가장 중요한 건 **R(Result)의 정량적 수치**입니다. "개선했습니다"가 아니라 "38fps→58fps, 메모리 68% 감소"처럼 숫자로 말하세요. 면접관은 임팩트를 측정할 수 있는 엔지니어를 원합니다.


---


## 💬 꼬리 질문 (면접 답변)


### Q1. 시스템 설계 면접에서 가장 먼저 해야 할 것은? `[기본 / 빈출]`

**요구사항을 명확히 하는 것입니다.**

바로 설계를 시작하면 안 됩니다. 2~3분간 질문하세요:
• 핵심 기능은 무엇인가? (MVP 범위)
• 사용자 규모는? (성능 요구사항)
• 오프라인 지원이 필요한가?
• 실시간성이 중요한가?

이 과정이 면접관에게 '문제를 정의할 줄 아는 사람'이라는 인상을 줍니다.


### Q2. iOS 시스템 설계에서 자주 나오는 주제는? `[기본 / 빈출]`

**Top 5 주제:**

1. **Feed/Timeline**: 페이지네이션, 이미지 캐싱, 오프라인
2. **Chat/Messaging**: WebSocket, 오프라인 큐, 순서 보장
3. **Image/Video Upload**: 청크 업로드, 재시도, 진행률
4. **Search**: 자동완성, debounce, 캐싱 전략
5. **Notification System**: Push, 로컬 알림, 딥링크

각 주제에 대해 아키텍처 다이어그램을 미리 준비해두면 좋습니다.


### Q3. STAR-T에서 Result를 정량적으로 말하는 이유는? `[기본 / 빈출]`

**임팩트를 객관적으로 증명하기 위해서입니다.**

'성능을 개선했습니다'는 주관적이고 검증 불가능합니다. '프레임 레이트를 38fps에서 58fps로 개선했습니다'는 명확하고 인상적입니다.

정량화할 수 있는 것들:
• 성능: fps, 응답시간, 메모리 사용량
• 비즈니스: 이탈률, 전환율, DAU
• 개발: 빌드 시간, 버그 수, PR 리뷰 시간
• 팀: 온보딩 시간, 만족도 점수


### Q4. 면접에서 모르는 질문이 나왔을 때 어떻게 대응하나요? `[심화 / 빈출]`

**솔직하게 인정하되, 사고 과정을 보여주세요.**

좋은 대응:
1. '정확히는 모르지만, 제가 아는 것을 바탕으로 추론해보겠습니다'
2. 관련된 개념에서 출발하여 논리적으로 접근
3. '실무에서 이 상황을 만나면 이렇게 조사할 것 같습니다'

나쁜 대응:
• 아는 척하다가 틀리기
• '모릅니다'로 끝내기
• 완전히 다른 주제로 넘어가기

면접관은 '모든 것을 아는 사람'이 아니라 '모르는 것을 해결할 수 있는 사람'을 찾습니다.


---


## ✏️ 퀴즈


### 문제 1

시스템 설계 면접의 올바른 진행 순서는?


   **A.** 바로 코드 작성 → 설명

✅ **B.** 요구사항 명확화 → 고수준 설계 → 상세 설계 → 트레이드오프

   **C.** 상세 설계 → 고수준 설계 → 요구사항

   **D.** 트레이드오프 → 설계 → 구현


**정답**: B


💡 **힌트**: 큰 그림에서 시작하여 점점 상세하게 들어가는 Top-down 접근이 효과적입니다.


### 문제 2

STAR-T 프레임워크에서 T(Takeaway)의 역할은?


   **A.** 기술 스택을 설명한다

   **B.** 팀 구성을 소개한다

✅ **C.** 경험에서 배운 교훈과 성장을 보여준다

   **D.** 타임라인을 제시한다


**정답**: C


💡 **힌트**: 단순히 결과를 말하는 것을 넘어, 그 경험이 자신을 어떻게 성장시켰는지 보여줍니다.


