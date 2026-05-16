# Day 6 — UIKit 렌더링 파이프라인과 성능

**태그**: Core Animation · Off-Screen · TableView · Cell Reuse · Diffable Data Source

---

## 📝 핵심 정리


### 1. 렌더링 파이프라인

_아이콘: `blue`_


### 한 프레임이 화면에 나오기까지

화면에 픽셀이 그려지는 건 단순한 일이 아닙니다. 여러 프로세스와 GPU가 협력합니다.

```swift
// 프레임 렌더링 단계 (60fps 기준 16.67ms 안에)
//
// [App Process]
// 1. Layout (Auto Layout 계산)
// 2. Display (draw 호출, 텍스트 렌더링)
// 3. Prepare (이미지 디코딩, GPU 업로드)
// 4. Commit (CALayer 트리 직렬화)
//        ──IPC 전송──→
//
// [Render Server (backboardd 프로세스)]
// 5. Layer tree 역직렬화
// 6. 렌더링 명령 생성 (Core Animation)
//        ──전송──→
//
// [GPU]
// 7. 실제 렌더링 (vertex/fragment shader)
// 8. 합성 (compositing)
// 9. 다음 VSync 신호에 디스플레이로 전송
//
// 총 예산: 16.67ms (60Hz) 또는 8.33ms (120Hz ProMotion)
// 앱 단계: ~10ms 권장
```

### 왜 Render Server가 별도 프로세스인가요?

앱이 크래시해도 시스템 UI는 계속 동작해야 하기 때문입니다. 또한 여러 앱의 UI를 합성하려면 중앙에서 관리하는 게 효율적입니다.

### Core Animation의 역할

Core Animation은 "선언적 애니메이션 + GPU 가속" 프레임워크입니다. UIView의 모든 시각 속성(frame, alpha, transform 등)은 사실 CALayer의 속성입니다.

```swift
// UIView는 사실 CALayer의 래퍼
view.alpha = 0.5
// → view.layer.opacity = 0.5
// → CALayer가 GPU에 전달
// → GPU가 알파 블렌딩 처리
```

> 💡 **💡 면접 포인트:** "iOS의 렌더링은 앱 → Render Server → GPU의 3단계 파이프라인입니다. 앱은 layer 트리를 만들어 IPC로 전달하고, Render Server가 GPU 명령으로 변환합니다. 이 분리 덕분에 앱이 응답 없어도 시스템 UI는 동작하지만, 매 프레임 IPC 비용이 발생하므로 commit 빈도를 줄이는 게 성능에 중요합니다."


### 2. Off-Screen Rendering (오프스크린 렌더링)

_아이콘: `green`_


### Off-Screen Rendering이 뭔가요?

"GPU가 메인 화면 버퍼가 아닌 별도의 임시 버퍼에 먼저 그린 후, 그 결과를 다시 메인 버퍼에 합성"하는 동작입니다. 추가 렌더링 패스가 발생해 비용이 큽니다.

### 비용 구조

- 임시 버퍼 메모리 할당

- GPU 컨텍스트 스위칭

- 임시 버퍼에 렌더링

- 다시 메인 버퍼에 합성

한두 번이면 무시할 수준이지만, 셀 50개에 다 발생하면 프레임 드롭의 주범이 됩니다.

### 오프스크린을 유발하는 것들

### 1. cornerRadius + masksToBounds

```swift
// ❌ 오프스크린 렌더링 발생!
imageView.layer.cornerRadius = 10
imageView.layer.masksToBounds = true
// 마스크를 적용하려면 일단 그려보고 잘라내야 하니까

// ✅ iOS 13+ 해결책: cornerCurve
imageView.layer.cornerRadius = 10
imageView.layer.cornerCurve = .continuous  // GPU 가속
// 또는 미리 둥글게 처리한 이미지 사용
```

### 2. shadow without shadowPath

```swift
// ❌ shadow 모양 계산을 위해 오프스크린
view.layer.shadowColor = UIColor.black.cgColor
view.layer.shadowOffset = CGSize(width: 0, height: 2)
view.layer.shadowOpacity = 0.5

// ✅ shadowPath 명시!
view.layer.shadowPath = UIBezierPath(
    roundedRect: view.bounds,
    cornerRadius: 10
).cgPath
// shadowPath가 있으면 GPU가 미리 알고 있어서 오프스크린 없이 처리
```

### 3. Mask Layer

```swift
// 항상 오프스크린
view.layer.mask = someMaskLayer
```

### 4. Group Opacity

```swift
// alpha < 1 + subview 있을 때 오프스크린 가능
view.alpha = 0.5
view.layer.allowsGroupOpacity = true
```

### 탐지 방법: Color Off-Screen-Rendered

시뮬레이터의 Debug 메뉴 → Color Off-Screen-Rendered. 노란색으로 표시되는 영역이 오프스크린 렌더링 중입니다.

### 이미지 미리 처리

```swift
// 백그라운드에서 둥근 이미지 미리 만들기
extension UIImage {
    func withRoundedCorners(radius: CGFloat) -> UIImage {
        let renderer = UIGraphicsImageRenderer(size: size)
        return renderer.image { ctx in
            let rect = CGRect(origin: .zero, size: size)
            UIBezierPath(roundedRect: rect, cornerRadius: radius).addClip()
            self.draw(in: rect)
        }
    }
}
// 이미지 자체를 둥글게 → cornerRadius 불필요 → 오프스크린 없음
```

> 💡 **💡 면접 포인트:** "TableView 셀에 cornerRadius + clipsToBounds를 쓰는 흔한 패턴이 스크롤 성능을 망치는 주범입니다. shadowPath를 명시하거나, iOS 13+의 cornerCurve를 쓰거나, 이미지를 미리 둥글게 처리하는 등의 방법으로 오프스크린을 피해야 합니다."


### 3. UITableView/UICollectionView 성능

_아이콘: `purple`_


### Cell Reuse 메커니즘

화면에 보이는 셀만 메모리에 유지하고, 화면 밖으로 나간 셀은 재사용 풀에 들어갑니다.

```swift
// dequeueReusableCell 동작:
// 1. reuse pool에서 같은 identifier의 셀 검색
// 2. 있으면: prepareForReuse() 호출 → 반환
// 3. 없으면: 새 셀 생성 (init 또는 nib 로드)

class MyCell: UITableViewCell {
    override func prepareForReuse() {
        super.prepareForReuse()
        // ⚠️ 여기서 이전 상태 초기화 필수!
        imageView.image = nil           // 이전 이미지 제거
        imageView.cancelDownload()      // 진행 중인 네트워크 취소
        disposeBag = DisposeBag()       // RxSwift 구독 해제
    }
}
```

### Self-Sizing Cell의 비용

```swift
// estimatedRowHeight 미설정 시:
// 모든 셀의 높이를 한 번씩 계산해야 함 → 첫 로딩 느림

// ✅ 추정값 제공
tableView.estimatedRowHeight = 80
tableView.rowHeight = UITableView.automaticDimension

// 더 빠른 방법: 높이 캐싱
var heightCache: [IndexPath: CGFloat] = [:]

func tableView(_ tv: UITableView, willDisplay cell: UITableViewCell, forRowAt ip: IndexPath) {
    heightCache[ip] = cell.frame.height
}

func tableView(_ tv: UITableView, estimatedHeightForRowAt ip: IndexPath) -> CGFloat {
    return heightCache[ip] ?? 80
}
```

### Prefetching (iOS 10+)

스크롤 방향을 예측하여 미리 데이터를 준비합니다.

```swift
extension VC: UITableViewDataSourcePrefetching {
    func tableView(_ tv: UITableView, prefetchRowsAt indexPaths: [IndexPath]) {
        let urls = indexPaths.compactMap { items[$0.row].imageURL }
        ImagePrefetcher(urls: urls).start()  // 미리 다운로드
    }
    
    func tableView(_ tv: UITableView, cancelPrefetchingForRowsAt ips: [IndexPath]) {
        // 스크롤 방향 변경 → 불필요한 프리페치 취소
    }
}

tableView.prefetchDataSource = self
```

### Diffable Data Source (iOS 13+)

기존 reload/insert/delete 호출의 크래시 위험을 없애고, 자동 diff + 애니메이션을 제공합니다.

```swift
var dataSource: UITableViewDiffableDataSource<Section, Item>!

dataSource = UITableViewDiffableDataSource(tableView: tableView) { tv, ip, item in
    let cell = tv.dequeueReusableCell(withIdentifier: "Cell", for: ip)
    cell.textLabel?.text = item.title
    return cell
}

func update(items: [Item]) {
    var snapshot = NSDiffableDataSourceSnapshot<Section, Item>()
    snapshot.appendSections([.main])
    snapshot.appendItems(items)
    dataSource.apply(snapshot, animatingDifferences: true)
    // 내부적으로 Myers diff 알고리즘으로 변경분만 적용
}
```

> 💡 **💡 면접 포인트:** "대규모 피드 화면에선 prepareForReuse에서 이전 상태를 깨끗이 정리하는 게 핵심입니다. 이미지 다운로드 취소를 안 하면 잘못된 셀에 이미지가 표시되는 버그가 자주 생기죠. 또한 Diffable Data Source로 마이그레이션하면 불일치로 인한 크래시가 사라지고 애니메이션도 자연스러워집니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. 오프스크린 렌더링이 무엇이고 어떻게 탐지하나요? `[심화 / 빈출]`

GPU가 메인 화면 버퍼가 아닌 임시 버퍼에 먼저 그린 후 합성하는 동작입니다. 추가 렌더링 패스가 발생해 성능에 좋지 않습니다.

주요 원인: cornerRadius + masksToBounds, shadowPath 미설정, mask layer.

탐지: 시뮬레이터의 Debug → Color Off-Screen-Rendered. 노란색 영역이 오프스크린 렌더링 중. Instruments의 Core Animation도 확인 가능.


### Q2. prepareForReuse에서 무엇을 해야 하나요? `[기본 / 빈출]`

셀이 재사용되기 직전 호출되므로, 이전 상태를 깨끗이 초기화해야 합니다.

1. `imageView.image = nil` (깜빡임 방지)
2. 진행 중인 이미지 다운로드 취소
3. RxSwift DisposeBag 재생성
4. Combine subscriptions 정리
5. 애니메이션 취소
6. 텍스트/색상 등 변경된 속성 원복

주의: 무거운 초기화(제약 조건 생성 등)는 init에서 한 번만, prepareForReuse에선 가벼운 리셋만.


### Q3. Diffable Data Source의 장점은? `[기본 / 빈출]`

1. **크래시 방지**: 기존 insertRows/deleteRows의 numberOfRows 불일치 크래시가 사라짐
2. **자동 diff**: snapshot만 제공하면 내부에서 Myers 알고리즘으로 최소 변경분 계산
3. **자동 애니메이션**: animatingDifferences로 자연스러운 전환
4. **type-safe**: Section/Item 타입을 generic으로 명시

iOS 13+ 신규 코드라면 거의 항상 Diffable이 정답입니다.


### Q4. shadowPath를 명시하는 이유는? `[심화]`

shadowPath 없이 shadow를 적용하면, 시스템이 매 프레임마다 view의 alpha 채널을 분석해 shadow shape을 계산합니다. 이 계산이 오프스크린 렌더링을 유발해 성능이 떨어집니다.

shadowPath를 미리 만들어주면 GPU가 shape을 알고 있어 직접 그리므로 오프스크린이 없습니다.

```swift
view.layer.shadowPath = UIBezierPath(\n    roundedRect: view.bounds,\n    cornerRadius: 10\n).cgPath
```


---


## ✏️ 퀴즈


### 문제 1

다음 중 오프스크린 렌더링을 유발하지 **않는** 것은?


   **A.** cornerRadius + masksToBounds = true

✅ **B.** shadowPath가 명시된 그림자

   **C.** mask layer 적용

   **D.** shadowPath 없는 shadow


**정답**: B


💡 **힌트**: shadowPath가 있으면 GPU가 모양을 미리 알고 있어 오프스크린 없이 그릴 수 있습니다.


### 문제 2

prepareForReuse를 호출하는 시점은?


   **A.** 셀이 처음 생성될 때

   **B.** 셀이 화면에 표시되기 직전

   **C.** 셀이 화면에서 사라진 후 재사용 풀로 들어갈 때

✅ **D.** 셀이 dequeueReusableCell로 다시 꺼내져 재사용되기 직전


**정답**: D


💡 **힌트**: 이름 그대로 \"재사용 준비\"입니다. 화면에 다시 표시되기 직전 호출됩니다.


