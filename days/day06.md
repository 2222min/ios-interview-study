# Day 6 — UIKit 렌더링 파이프라인과 성능

**태그**: Core Animation · Off-Screen · TableView · Cell Reuse · Diffable Data Source

---

## 📝 핵심 정리

## 1. 렌더링 파이프라인

### 한 프레임이 화면에 나오기까지

화면에 픽셀이 그려지는 건 단순한 일이 아닙니다. UIKit은 변경사항을 즉시 픽셀로 그리는 방식이 아니라, Main Thread RunLoop의 업데이트 사이클에서 View/Layer 변경사항을 모아 처리하고, Core Animation이 이를 Render Server와 GPU로 넘겨 최종 화면을 만듭니다.

```swift
// 프레임 렌더링 단계 (60fps 기준 16.67ms 안에)
//
// [App Process / Main Thread RunLoop]
// 1. Layout  : Auto Layout, frame/bounds 계산, layoutSubviews()
// 2. Display : draw(_:) 호출 가능, 텍스트/커스텀 드로잉 준비
// 3. Prepare : 이미지 디코딩, 텍스처 업로드 등 GPU 리소스 준비
// 4. Commit  : 변경된 CALayer Tree를 Core Animation transaction으로 묶음
//        ──IPC 전송──→
//
// [Render Server (backboardd 프로세스)]
// 5. Layer Tree 처리
// 6. Layer Tree를 바탕으로 GPU 렌더링 명령 생성
//        ──전송──→
//
// [GPU]
// 7. 실제 렌더링
// 8. 여러 Layer 합성(compositing)
// 9. 다음 VSync 타이밍에 디스플레이로 표시
//
// 총 예산: 16.67ms (60Hz) 또는 8.33ms (120Hz ProMotion)
// 앱 단계: ~10ms 권장
```

> 핵심은 앱이 Render Server에 **Layout Tree**를 넘기는 것이 아니라, 변경된 **CALayer Tree**를 넘긴다는 점입니다. Render Server는 이 Layer Tree를 GPU가 이해할 수 있는 렌더링 명령으로 바꾸고, GPU가 렌더링과 합성을 수행합니다.

### RunLoop 업데이트 사이클과 연결

`view.backgroundColor`, `constraint.constant`, `label.text` 같은 값을 바꿨다고 해서 그 순간 바로 화면 픽셀이 바뀌는 것은 아닙니다. 대부분의 변경은 "레이아웃 필요", "디스플레이 필요" 상태로 표시되고, RunLoop가 잠들기 전 업데이트 사이클에서 Layout/Display/Commit이 한 번에 처리됩니다.

```swift
heightConstraint.constant = 200
view.setNeedsLayout()        // 다음 layout pass 예약
customView.setNeedsDisplay() // 다음 display pass에서 draw(_:) 예약

// 필요한 경우 지금 즉시 layout pass 수행
view.layoutIfNeeded()
```

- `setNeedsLayout()`은 위치와 크기 계산이 다시 필요하다고 표시합니다. 다음 layout pass에서 `layoutSubviews()`가 호출될 수 있습니다.
- `layoutIfNeeded()`는 현재 레이아웃이 dirty 상태라면 다음 RunLoop까지 기다리지 않고 즉시 layout pass를 수행합니다. 제약 변경 애니메이션에서 자주 사용합니다.
- `setNeedsDisplay()`는 레이아웃이 아니라 drawing이 다시 필요하다고 표시합니다. 다음 display pass에서 `draw(_:)`가 호출될 수 있습니다.

### layoutSubviews()와 draw(_:)의 차이

`layoutSubviews()`는 subview의 위치와 크기를 배치하는 함수이고, `draw(_:)`는 Core Graphics로 실제 콘텐츠를 직접 그리는 함수입니다. 즉, **layoutSubviews는 배치**, **draw는 그리기**입니다.

```swift
override func layoutSubviews() {
    super.layoutSubviews()
    imageView.frame = bounds        // 배치
}

override func draw(_ rect: CGRect) {
    UIColor.red.setFill()
    UIBezierPath(ovalIn: rect).fill() // 그리기
}
```

`draw(_:)`는 Display 단계에서 호출될 수 있으며, 도형/선/텍스트/이미지 등을 CPU에서 Core Graphics로 backing store에 그리는 작업입니다. 셀에서 복잡한 `draw(_:)`가 반복되면 Display 단계의 CPU 비용이 커져 스크롤 성능에 영향을 줄 수 있습니다. 단순한 선, 원, progress 같은 UI는 `draw(_:)` 대신 `CAShapeLayer`를 사용하면 path 기반으로 Core Animation이 관리할 수 있어 더 적합한 경우가 많습니다.

### 왜 Render Server가 별도 프로세스인가요?

앱이 크래시해도 시스템 UI는 계속 동작해야 하기 때문입니다. 또한 여러 앱의 UI를 합성하려면 중앙에서 관리하는 게 효율적입니다. 앱 프로세스와 Render Server는 서로 다른 프로세스이므로 직접 메서드 호출처럼 통신할 수 없습니다. 그래서 Core Animation은 Commit 단계에서 변경된 Layer Tree를 **IPC(Inter-Process Communication)** 로 Render Server에 전달합니다.

### Core Animation의 역할

Core Animation은 "선언적 애니메이션 + GPU 가속" 프레임워크입니다. UIView의 모든 시각 속성(frame, alpha, transform 등)은 사실 CALayer의 속성입니다.

```swift
// UIView는 사실 CALayer의 래퍼
view.alpha = 0.5
// → view.layer.opacity = 0.5
// → CALayer가 GPU에 전달
// → GPU가 알파 블렌딩 처리
```

> 💡 **면접 포인트**: "iOS의 렌더링은 앱 → Render Server → GPU의 3단계 파이프라인입니다. 앱은 Main Thread RunLoop의 업데이트 사이클에서 Layout, Display, Prepare, Commit을 처리하고, 변경된 CALayer Tree를 IPC로 Render Server에 전달합니다. Render Server는 이를 GPU 명령으로 변환하고, GPU는 렌더링과 합성을 수행한 뒤 다음 VSync 타이밍에 화면에 표시합니다."

---

## 2. Off-Screen Rendering (오프스크린 렌더링)

### Off-Screen Rendering이 뭔가요?

GPU가 메인 화면 버퍼가 아닌 별도의 임시 버퍼에 먼저 그린 후, 그 결과를 다시 메인 버퍼에 합성하는 동작입니다. 추가 렌더링 패스가 발생해 비용이 큽니다.

비용 구조는 다음과 같습니다.

- 임시 버퍼 메모리 할당
- GPU 컨텍스트 스위칭
- 임시 버퍼에 렌더링
- 다시 메인 버퍼에 합성

한두 번이면 무시할 수준이지만, 셀 50개에 다 발생하면 프레임 드롭의 주범이 됩니다.

### 오프스크린을 유발하는 대표적인 케이스

**1) cornerRadius + masksToBounds**

```swift
// ❌ 오프스크린 렌더링 발생 가능
imageView.layer.cornerRadius = 10
imageView.layer.masksToBounds = true
// 또는 imageView.clipsToBounds = true
```

`cornerRadius` 자체가 항상 문제라기보다, `masksToBounds`/`clipsToBounds`와 함께 사용되어 내부 콘텐츠를 둥근 영역에 맞게 잘라야 할 때 비용이 커질 수 있습니다. 시스템은 내용을 임시 버퍼에 먼저 그리고, radius 모양의 mask를 적용한 뒤, 그 결과를 다시 메인 화면 버퍼에 합성해야 할 수 있습니다.

```swift
// ✅ 대안 1: 이미지를 백그라운드에서 미리 둥글게 처리
// ✅ 대안 2: clipping이 필요 없는 구조로 분리
// ✅ 대안 3: 셀처럼 반복되는 UI에서는 사용 범위 최소화
imageView.layer.cornerRadius = 10
imageView.layer.cornerCurve = .continuous
```

**2) shadow without shadowPath**

```swift
// ❌ shadow 모양 계산을 위해 오프스크린
view.layer.shadowColor = UIColor.black.cgColor
view.layer.shadowOffset = CGSize(width: 0, height: 2)
view.layer.shadowOpacity = 0.5

// ✅ shadowPath 명시
view.layer.shadowPath = UIBezierPath(
    roundedRect: view.bounds,
    cornerRadius: 10
).cgPath
```

`shadowPath`의 핵심은 그림자의 모양을 시스템이 추측하지 않게 개발자가 명시적으로 알려주는 것입니다. `shadowPath`가 없으면 Core Animation이 Layer의 alpha 영역을 분석해 shadow shape을 계산해야 할 수 있고, 이 과정에서 오프스크린 렌더링이 발생할 수 있습니다.

**3) Mask Layer**

```swift
// 항상 오프스크린
view.layer.mask = someMaskLayer
```

**4) Group Opacity**

```swift
// alpha 자체가 항상 오프스크린을 유발하는 것은 아님
// 여러 subview를 하나의 그룹처럼 투명 처리해야 하는 경우 비용이 커질 수 있음
view.alpha = 0.5
view.layer.allowsGroupOpacity = true
```

`alpha < 1`은 보통 알파 블렌딩 비용으로 이해하는 것이 더 정확합니다. 다만 여러 subview를 가진 그룹 전체에 opacity를 적용해야 하는 경우에는 먼저 그룹을 임시 버퍼에 그리고, 그 결과에 alpha를 적용해야 할 수 있습니다.

### 탐지 방법: Color Off-Screen-Rendered

시뮬레이터의 Debug 메뉴 → Color Off-Screen-Rendered. 노란색으로 표시되는 영역이 오프스크린 렌더링 중입니다. Instruments의 Core Animation 템플릿에서도 확인할 수 있습니다.

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

> 💡 **면접 포인트**: "오프스크린 렌더링은 GPU가 바로 화면 버퍼에 그리지 못하고 임시 버퍼에 먼저 렌더링한 뒤 다시 합성하는 과정입니다. `cornerRadius + masksToBounds`, `shadowPath` 없는 shadow, mask layer, group opacity 상황이 대표적입니다. 셀처럼 반복되는 UI에서 많이 발생하면 GPU 합성 비용이 커져 스크롤 성능이 떨어질 수 있습니다."

---

## 3. UITableView/UICollectionView 성능

### Cell Reuse 메커니즘

화면에 보이는 셀만 메모리에 유지하고, 화면 밖으로 나간 셀은 재사용 풀에 들어갑니다.

```swift
// dequeueReusableCell 동작:
// 1. reuse pool에서 같은 identifier의 셀 검색
// 2. 있으면: prepareForReuse() 호출 → 반환
// 3. 없으면: 새 셀 생성 (init 또는 nib 로드)

class MyCell: UITableViewCell {
    private var imageTask: URLSessionDataTask?
    private var currentImageURL: URL?
    var disposeBag = DisposeBag()

    override func prepareForReuse() {
        super.prepareForReuse()
        // ⚠️ 여기서 이전 상태 초기화 필수
        titleLabel.text = nil
        imageView.image = nil           // 이전 이미지 제거
        badgeView.isHidden = true       // hidden/selected/highlight 상태 원복

        imageTask?.cancel()             // 진행 중인 네트워크 취소
        imageTask = nil
        currentImageURL = nil

        disposeBag = DisposeBag()       // RxSwift 구독 해제
    }
}
```

이미지 다운로드를 취소하지 않으면, 이전 데이터 기준으로 시작된 비동기 요청이 셀 재사용 이후에도 살아 있다가 새 데이터가 바인딩된 셀에 잘못된 이미지를 넣을 수 있습니다. 취소만으로 부족한 경우가 있으므로 콜백 시점에 `currentImageURL == responseURL`처럼 현재 셀이 여전히 같은 데이터를 표현하는지도 확인하는 것이 안전합니다.

RxSwift를 사용하는 셀에서는 이전 데이터 기준으로 만들어진 구독이 살아 있으면 중복 바인딩이나 잘못된 UI 업데이트가 발생할 수 있습니다. 그래서 `prepareForReuse()`에서 `disposeBag = DisposeBag()`으로 셀 데이터 바인딩과 관련된 구독을 끊고, `configure` 시점에 새 데이터 기준으로 다시 바인딩합니다.

### Self-Sizing Cell의 비용

Self-Sizing Cell은 Auto Layout을 기반으로 실제 셀 높이를 계산합니다. 구현은 편하지만 셀 내부 제약이 복잡하거나 뷰 계층이 깊으면 높이 계산 비용이 커질 수 있습니다. 또한 `estimatedRowHeight`가 실제 높이와 많이 다르면 contentSize 재계산, 스크롤 위치 보정, 레이아웃 재계산이 발생해 스크롤바가 튀거나 버벅일 수 있습니다.

```swift
// estimatedRowHeight 미설정 시:
// 모든 셀의 높이를 한 번씩 계산해야 함 → 첫 로딩 느림

// ✅ 실제 평균 높이에 가까운 추정값 제공
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

`UICollectionViewCompositionalLayout`에서도 원리는 같습니다. `estimated(1)`처럼 실제 셀 높이와 차이가 큰 값을 주면 초기 contentSize와 실제 레이아웃 결과 차이가 커져 invalidation과 스크롤 보정이 늘어날 수 있습니다. 동적 높이가 필요하다면 item과 group의 height를 모두 `estimated`로 두되, 실제 평균 높이에 가까운 값을 주는 것이 좋습니다.

```swift
let itemSize = NSCollectionLayoutSize(
    widthDimension: .fractionalWidth(1.0),
    heightDimension: .estimated(120)
)
let item = NSCollectionLayoutItem(layoutSize: itemSize)

let groupSize = NSCollectionLayoutSize(
    widthDimension: .fractionalWidth(1.0),
    heightDimension: .estimated(120)
)
let group = NSCollectionLayoutGroup.vertical(
    layoutSize: groupSize,
    subitems: [item]
)
```

### Prefetching (iOS 10+)

스크롤 방향을 예측하여 곧 화면에 나타날 indexPath의 데이터나 리소스를 미리 준비합니다. 이미지 다운로드, 썸네일 준비, 페이지네이션 요청처럼 셀이 실제로 보이는 시점에 시작하면 늦을 수 있는 작업에 적합합니다. 단, 스크롤 방향이 바뀌면 필요 없는 요청이 생길 수 있으므로 반드시 취소 흐름을 함께 설계해야 합니다.

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

기존 reload/insert/delete 호출의 크래시 위험을 줄이고, snapshot 기반으로 데이터 상태를 선언적으로 관리할 수 있습니다. 기존 indexPath 기반 batch update는 실제 data source 개수와 UI 업데이트 호출이 어긋나면 `Invalid update` 크래시가 발생할 수 있습니다. Diffable은 이전 snapshot과 새 snapshot을 비교해 insert/delete/move 같은 변경분을 계산하고 적용합니다.

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
    // 이전 snapshot과 새 snapshot을 비교해 변경분 적용
}
```

`reloadData()`는 리스트 전체를 다시 로드하는 명령에 가깝습니다. 보이는 셀 구성, 레이아웃 계산, display 작업이 다시 발생할 수 있어 스크롤 중 자주 호출하면 UX가 나빠질 수 있습니다. 반면 Diffable의 `apply(snapshot:)`은 이전 상태와 새 상태를 비교해 필요한 변경을 적용하므로 변경분 애니메이션과 안정성 측면에서 유리합니다.

주의할 점은 `Hashable` 설계입니다. Diffable은 `Hashable`을 기반으로 아이템의 동일성(identity)을 판단합니다. 같은 아이템인데 매번 다른 hash가 나오면 불필요한 delete/insert와 깜빡임이 생길 수 있고, 반대로 실제 내용이 바뀌었는데 변경을 인지하지 못하면 UI가 갱신되지 않을 수 있습니다. 보통 안정적인 `id`로 identity를 잡고, 같은 아이템의 내용만 바뀐 경우에는 `reloadItems` 또는 iOS 15+의 `reconfigureItems`를 명시적으로 사용합니다.

```swift
// iOS 15+ : 기존 셀을 최대한 유지하면서 content만 다시 configure
snapshot.reconfigureItems([item])
dataSource.apply(snapshot, animatingDifferences: true)

// 셀 높이/구조가 바뀌는 경우에는 reloadItems 고려
snapshot.reloadItems([item])
```

- `reloadItems`: 셀을 다시 로드하는 성격이 강합니다. 셀 높이, 레이아웃, 셀 타입이 바뀌는 경우에 적합합니다.
- `reconfigureItems`: 기존 셀을 유지한 채 content만 다시 설정하는 더 가벼운 방식입니다. 좋아요 수, 북마크 상태, 읽음 상태처럼 레이아웃 구조가 크게 바뀌지 않는 업데이트에 적합합니다.

### 스크롤 버벅임을 의심하는 순서

스크롤이 멈추거나 버벅이는 현상은 보통 Main Thread가 한 프레임 안에 다음 화면을 준비하지 못해서 발생합니다. 원인을 볼 때는 아래 순서로 확인하면 좋습니다.

1. `cellForRowAt` / `cellForItemAt`에서 동기 네트워크, 파일 IO, 이미지 디코딩, 복잡한 계산을 하고 있지 않은지 확인
2. 이미지 다운로드/디코딩/리사이징이 백그라운드에서 처리되고, 최종 UI 반영만 Main Thread에서 일어나는지 확인
3. Self-Sizing Cell의 estimated height가 실제 평균 높이와 많이 차이 나지 않는지 확인
4. Auto Layout 제약이 복잡하거나 View 계층이 깊지 않은지 확인
5. `cornerRadius + masksToBounds`, `shadowPath` 없는 shadow 등 오프스크린 렌더링이 많이 발생하지 않는지 확인
6. 스크롤 중 `reloadData()`나 `apply(snapshot:)`를 과도하게 호출하지 않는지 확인
7. `prepareForReuse()`에서 이전 비동기 작업과 구독을 정리하고 있는지 확인

> 💡 **면접 포인트**: "대규모 피드 화면에선 `prepareForReuse()`에서 이전 상태를 깨끗이 정리하는 게 핵심입니다. 이미지 다운로드 취소와 identity 검증을 하지 않으면 잘못된 셀에 이미지가 표시될 수 있습니다. 또한 스크롤 버벅임은 Main Thread 병목, 이미지 디코딩, Self-Sizing Cell, 오프스크린 렌더링, 과도한 reload/apply 호출을 순서대로 의심해볼 수 있습니다."

---

## 💬 꼬리 질문 & 면접 답변

### Q1. UIKit 렌더링 파이프라인을 설명해주세요.

UIKit 렌더링은 크게 앱 프로세스, Render Server, GPU 단계로 나눌 수 있습니다. 앱 프로세스에서는 Main Thread RunLoop의 업데이트 사이클에서 Layout, Display, Prepare, Commit이 처리됩니다. Layout은 View/Layer의 위치와 크기를 계산하고, Display는 `draw(_:)`나 텍스트 렌더링처럼 Layer에 표시할 콘텐츠를 준비합니다. Prepare는 이미지 디코딩이나 GPU 리소스 준비 단계이고, Commit에서는 변경된 CALayer Tree를 Core Animation transaction으로 묶어 IPC로 Render Server에 전달합니다. Render Server는 이를 GPU 명령으로 바꾸고, GPU가 렌더링과 합성을 수행한 뒤 다음 VSync 타이밍에 화면에 표시합니다.

---

### Q2. 오프스크린 렌더링이 무엇이고 어떻게 탐지하나요?

GPU가 메인 화면 버퍼가 아닌 임시 버퍼에 먼저 그린 후 합성하는 동작입니다. 추가 렌더링 패스와 임시 버퍼 비용이 발생해 성능에 좋지 않습니다. 주요 원인은 `cornerRadius + masksToBounds`, `shadowPath` 없는 shadow, mask layer, group opacity입니다. 단, `alpha`나 `cornerRadius` 자체가 항상 오프스크린을 유발한다고 말하기보다는 특정 조합에서 발생할 수 있다고 설명하는 것이 정확합니다.

탐지는 시뮬레이터의 Debug → Color Off-Screen-Rendered 옵션으로 합니다. 노란색 영역이 오프스크린 렌더링 중인 부분이고, Instruments의 Core Animation 템플릿에서도 확인할 수 있습니다.

---

### Q3. prepareForReuse에서 무엇을 해야 하나요?

셀이 재사용되기 직전 호출되므로, 이전 상태를 깨끗이 초기화해야 합니다.

1. `imageView.image = nil` (깜빡임 방지)
2. 진행 중인 이미지 다운로드 취소
3. RxSwift DisposeBag 재생성
4. Combine subscriptions 정리
5. 애니메이션 취소
6. 텍스트/색상 등 변경된 속성 원복

이미지 다운로드를 취소하지 않으면 비동기 콜백이 셀 재사용 이후에 도착해 잘못된 이미지를 셀에 넣을 수 있습니다. 취소만으로 부족한 경우 콜백 시점에 `currentImageURL == responseURL`로 identity를 한 번 더 검증하는 것이 안전합니다. 무거운 초기화(제약 조건 생성 등)는 init에서 한 번만 하고, prepareForReuse에서는 가벼운 리셋만 하는 것이 좋습니다.

---

### Q4. Diffable Data Source의 장점은?

1. **크래시 방지**: 기존 insertRows/deleteRows의 numberOfRows 불일치 크래시를 줄일 수 있음
2. **snapshot 기반 상태 관리**: 현재 UI 상태를 snapshot으로 선언적으로 표현
3. **자동 변경분 계산**: 이전 snapshot과 새 snapshot을 비교해 insert/delete/move 적용
4. **자동 애니메이션**: animatingDifferences로 자연스러운 전환
5. **type-safe**: Section/Item 타입을 generic으로 명시

주의할 점은 `Hashable` 설계입니다. 같은 아이템인데 매번 다른 hash가 나오면 불필요한 delete/insert가 발생할 수 있고, 반대로 내용이 바뀌었는데 갱신 의도를 전달하지 않으면 UI가 업데이트되지 않을 수 있습니다. 같은 아이템의 내용만 바뀌는 경우에는 `reloadItems` 또는 iOS 15+의 `reconfigureItems`를 고려합니다.

---

### Q5. shadowPath를 명시하는 이유는?

`shadowPath` 없이 shadow를 적용하면, 시스템이 매 프레임마다 view의 alpha 채널을 분석해 shadow shape을 계산해야 할 수 있습니다. 이 계산이 오프스크린 렌더링을 유발해 성능이 떨어집니다. `shadowPath`를 미리 만들어주면 GPU가 shape을 알고 있어 직접 그리므로 오프스크린이 없습니다.

```swift
view.layer.shadowPath = UIBezierPath(
    roundedRect: view.bounds,
    cornerRadius: 10
).cgPath
```

---

### Q6. setNeedsLayout, layoutIfNeeded, setNeedsDisplay의 차이는?

`setNeedsLayout()`은 위치와 크기 계산이 다시 필요하다고 표시만 하고, 다음 layout pass에서 `layoutSubviews()`가 호출되도록 예약합니다. `layoutIfNeeded()`는 레이아웃이 dirty 상태라면 다음 RunLoop를 기다리지 않고 즉시 layout pass를 수행합니다. 제약 변경 애니메이션에서 `constraint.constant` 변경 후 `animate` 블록 안에서 `layoutIfNeeded()`를 호출하는 패턴이 자주 쓰입니다. `setNeedsDisplay()`는 레이아웃이 아니라 drawing이 다시 필요하다고 표시하며, 다음 display pass에서 `draw(_:)`가 호출될 수 있도록 예약합니다.

---

### Q7. `reloadData()`와 Diffable의 `apply(snapshot:)`의 차이는?

`reloadData()`는 리스트 전체를 다시 로드하는 성격이 강합니다. 보이는 셀 구성, 레이아웃 계산, display 작업이 다시 발생할 수 있어 스크롤 중 자주 호출하면 UX가 나빠질 수 있고 셀 상태(스크롤 위치, 선택, 애니메이션 등)가 끊길 수 있습니다. 반면 Diffable의 `apply(snapshot:)`은 이전 snapshot과 새 snapshot을 비교해 insert/delete/move/reload 같은 변경분만 적용하므로 변경분 애니메이션과 안정성 측면에서 유리합니다. 같은 아이템의 내용만 바뀌었고 셀 구조나 높이가 그대로면 iOS 15+의 `reconfigureItems`를 사용해 기존 셀을 유지한 채 content만 다시 configure하는 것이 가장 가볍습니다.

---

## ✏️ 퀴즈

### 문제 1

다음 중 오프스크린 렌더링을 유발하지 **않는** 것은?

- A. cornerRadius + masksToBounds = true
- B. shadowPath가 명시된 그림자
- C. mask layer 적용
- D. shadowPath 없는 shadow

**정답: B**

💡 **힌트**: shadowPath가 있으면 GPU가 모양을 미리 알고 있어 오프스크린 없이 그릴 수 있습니다.

---

### 문제 2

prepareForReuse를 호출하는 시점은?

- A. 셀이 처음 생성될 때
- B. 셀이 화면에 표시되기 직전
- C. 셀이 화면에서 사라진 후 재사용 풀로 들어갈 때
- D. 셀이 dequeueReusableCell로 다시 꺼내져 재사용되기 직전

**정답: D**

💡 **힌트**: 이름 그대로 "재사용 준비"입니다. 화면에 다시 표시되기 직전 호출됩니다.

---

### 문제 3

`setNeedsLayout()`, `layoutIfNeeded()`, `setNeedsDisplay()`에 대한 설명으로 올바른 것은?

- A. setNeedsLayout()은 즉시 draw(_:)를 호출한다
- B. layoutIfNeeded()는 레이아웃이 필요한 상태라면 즉시 layout pass를 수행한다
- C. setNeedsDisplay()는 Auto Layout constraint를 즉시 계산한다
- D. 세 메서드는 모두 같은 역할이다

**정답: B**

💡 **힌트**: setNeedsLayout()과 setNeedsDisplay()는 dirty flag만 세우고, layoutIfNeeded()는 필요 시 즉시 layout을 수행합니다.

---

### 문제 4

Diffable Data Source에서 같은 아이템의 좋아요 수만 변경되었고 셀 구조나 높이는 그대로일 때 가장 적합한 방법은?

- A. 항상 reloadData() 호출
- B. 앱을 재시작
- C. iOS 15+의 reconfigureItems(_:) 사용 고려
- D. estimatedHeight를 1로 변경

**정답: C**

💡 **힌트**: reconfigureItems는 기존 셀을 최대한 유지하면서 content만 다시 configure하는 데 적합합니다.

---

### 문제 5

UIKit 렌더링 파이프라인에서 앱 프로세스가 Render Server로 전달하는 것은?

- A. Auto Layout 제약 그래프
- B. 변경된 CALayer Tree (Core Animation transaction)
- C. UIView 인스턴스 자체
- D. GPU 셰이더 코드

**정답: B**

💡 **힌트**: Commit 단계에서 변경된 Layer Tree가 IPC로 Render Server에 전달되고, Render Server가 이를 GPU 명령으로 변환합니다.
