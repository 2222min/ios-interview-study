# Day 16 — Image Processing & Caching

**태그**: Downsampling · ImageIO · NSCache · Memory Cost · Kingfisher · SDWebImage

---

## 📝 핵심 정리


### 1. Downsampling with ImageIO

_아이콘: `blue`_


### 왜 Downsampling이 필요한가요?

4000x3000 픽셀 사진을 100x100 UIImageView에 표시한다고 해봅시다. UIImage로 그냥 로드하면 **48MB(4000×3000×4bytes)**가 메모리에 올라갑니다. 실제 필요한 건 40KB(100×100×4bytes)뿐인데요.

### ImageIO를 사용한 효율적 Downsampling

```swift
import ImageIO

func downsample(imageAt url: URL, to pointSize: CGSize, scale: CGFloat) -> UIImage? {
    let maxDimensionInPixels = max(pointSize.width, pointSize.height) * scale
    
    let imageSourceOptions = [kCGImageSourceShouldCache: false] as CFDictionary
    guard let imageSource = CGImageSourceCreateWithURL(url as CFURL, imageSourceOptions) else {
        return nil
    }
    
    let downsampleOptions = [
        kCGImageSourceCreateThumbnailFromImageAlways: true,
        kCGImageSourceShouldCacheImmediately: true,
        kCGImageSourceCreateThumbnailWithTransform: true,
        kCGImageSourceThumbnailMaxPixelSize: maxDimensionInPixels
    ] as CFDictionary
    
    guard let downsampledImage = CGImageSourceCreateThumbnailAtIndex(imageSource, 0, downsampleOptions) else {
        return nil
    }
    
    return UIImage(cgImage: downsampledImage)
}

// 사용 예시
let thumbnailSize = CGSize(width: 100, height: 100)
let image = downsample(
    imageAt: imageURL,
    to: thumbnailSize,
    scale: UIScreen.main.scale  // @2x, @3x 대응
)
```

### UIImage(contentsOfFile:) vs ImageIO

| 항목 | UIImage | ImageIO |
|---|---|---|
| 메모리 | 전체 이미지 디코딩 | 필요한 크기만 디코딩 |
| 디코딩 시점 | 렌더링 시 (메인 스레드) | 명시적 제어 가능 |
| EXIF 회전 | 자동 처리 | CreateThumbnailWithTransform으로 처리 |

> 💡 **💡 면접 포인트:** "ImageIO의 CGImageSourceCreateThumbnailAtIndex는 전체 이미지를 메모리에 올리지 않고 필요한 크기로만 디코딩합니다. 컬렉션뷰에서 수백 개의 이미지를 표시할 때 메모리 사용량을 90% 이상 줄일 수 있습니다. kCGImageSourceShouldCache: false로 원본 캐싱을 방지하는 것이 핵심입니다."


### 2. NSCache 3-Level Caching 전략

_아이콘: `green`_


### 3단계 캐싱 구조

```swift
// Level 1: Memory Cache (NSCache)
// Level 2: Disk Cache (FileManager)
// Level 3: Network (URLSession)
//
// 조회 순서: Memory → Disk → Network
// 저장 순서: Network → Disk → Memory

class ImageCache {
    static let shared = ImageCache()
    
    // Level 1: 메모리 캐시
    private let memoryCache: NSCache<NSString, UIImage> = {
        let cache = NSCache<NSString, UIImage>()
        cache.countLimit = 100           // 최대 100개
        cache.totalCostLimit = 50 * 1024 * 1024  // 50MB
        return cache
    }()
    
    // Level 2: 디스크 캐시
    private let diskCacheURL: URL = {
        let paths = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)
        return paths[0].appendingPathComponent("ImageCache")
    }()
    
    func image(for url: URL) async -> UIImage? {
        let key = url.absoluteString as NSString
        
        // Level 1: 메모리 확인
        if let cached = memoryCache.object(forKey: key) {
            return cached
        }
        
        // Level 2: 디스크 확인
        let diskPath = diskCacheURL.appendingPathComponent(key.hash.description)
        if let diskImage = UIImage(contentsOfFile: diskPath.path) {
            memoryCache.setObject(diskImage, forKey: key, cost: diskImage.memoryCost)
            return diskImage
        }
        
        // Level 3: 네트워크
        guard let (data, _) = try? await URLSession.shared.data(from: url),
              let image = UIImage(data: data) else {
            return nil
        }
        
        // 캐시 저장
        memoryCache.setObject(image, forKey: key, cost: image.memoryCost)
        try? data.write(to: diskPath)
        
        return image
    }
}
```

### NSCache의 특징

- **Thread-safe**: 별도 동기화 없이 여러 스레드에서 접근 가능

- **Auto-eviction**: 메모리 압박 시 자동으로 항목 제거

- **Cost 기반 관리**: totalCostLimit으로 메모리 상한 설정

- **Dictionary와 차이**: 키를 strong 참조하지 않음, 메모리 경고 시 자동 정리

### 이미지 메모리 비용 계산

```swift
extension UIImage {
    var memoryCost: Int {
        guard let cgImage = self.cgImage else { return 0 }
        return cgImage.bytesPerRow * cgImage.height
        // = width * height * 4 (RGBA, 픽셀당 4바이트)
    }
}

// 예시:
// 1920x1080 이미지 = 1920 * 1080 * 4 = 8,294,400 bytes ≈ 8MB
// 100x100 썸네일 = 100 * 100 * 4 = 40,000 bytes ≈ 40KB
```

> 💡 **💡 면접 답변:** "3단계 캐싱으로 Memory → Disk → Network 순서로 조회합니다. NSCache는 thread-safe하고 메모리 압박 시 자동 정리됩니다. cost를 이미지의 실제 메모리 크기(width×height×4)로 설정하여 totalCostLimit으로 메모리 상한을 관리합니다."


### 3. Kingfisher / SDWebImage 패턴

_아이콘: `orange`_


### Kingfisher 핵심 아키텍처

```swift
// Kingfisher 사용법
import Kingfisher

imageView.kf.setImage(
    with: url,
    placeholder: UIImage(named: "placeholder"),
    options: [
        .processor(DownsamplingImageProcessor(size: imageView.bounds.size)),
        .scaleFactor(UIScreen.main.scale),
        .cacheOriginalImage,
        .transition(.fade(0.3))
    ],
    completionHandler: { result in
        switch result {
        case .success(let value):
            print("캐시 타입: \\(value.cacheType)")  // .memory, .disk, .none
        case .failure(let error):
            print("에러: \\(error)")
        }
    }
)

// 캐시 관리
ImageCache.default.memoryStorage.config.totalCostLimit = 300 * 1024 * 1024
ImageCache.default.diskStorage.config.sizeLimit = 1000 * 1024 * 1024
ImageCache.default.diskStorage.config.expiration = .days(7)

// 캐시 정리
ImageCache.default.clearMemoryCache()
ImageCache.default.clearDiskCache { print("디스크 캐시 정리 완료") }
```

### UICollectionView에서의 이미지 처리 패턴

```swift
class ImageCell: UICollectionViewCell {
    private let imageView = UIImageView()
    
    override func prepareForReuse() {
        super.prepareForReuse()
        // 재사용 시 이전 다운로드 취소 (중요!)
        imageView.kf.cancelDownloadTask()
        imageView.image = nil
    }
    
    func configure(with url: URL) {
        imageView.kf.setImage(
            with: url,
            options: [
                .processor(DownsamplingImageProcessor(size: imageView.bounds.size)),
                .scaleFactor(UIScreen.main.scale),
                .transition(.fade(0.2)),
                .cacheOriginalImage
            ]
        )
    }
}

// Prefetching으로 스크롤 성능 향상
extension ViewController: UICollectionViewDataSourcePrefetching {
    func collectionView(_ collectionView: UICollectionView, 
                       prefetchItemsAt indexPaths: [IndexPath]) {
        let urls = indexPaths.compactMap { items[$0.item].imageURL }
        ImagePrefetcher(urls: urls).start()
    }
    
    func collectionView(_ collectionView: UICollectionView, 
                       cancelPrefetchingForItemsAt indexPaths: [IndexPath]) {
        let urls = indexPaths.compactMap { items[$0.item].imageURL }
        ImagePrefetcher(urls: urls).stop()
    }
}
```

> 💡 **💡 면접 답변:** "Kingfisher는 다운로드, 캐싱, 이미지 처리를 통합 관리합니다. prepareForReuse에서 이전 다운로드를 취소하여 셀 재사용 시 잘못된 이미지가 표시되는 것을 방지합니다. Prefetching으로 스크롤 전에 미리 다운로드하여 사용자 경험을 향상시킵니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. 이미지 메모리 비용은 어떻게 계산하나요? `[기본 / 빈출]`

**width × height × bytesPerPixel**입니다.

RGBA 포맷(가장 일반적)은 픽셀당 4바이트입니다:
• 1920×1080 = 약 8MB
• 4000×3000 = 약 48MB
• 100×100 = 약 40KB

중요: 파일 크기(JPEG 200KB)와 메모리 크기(8MB)는 완전히 다릅니다. JPEG은 압축된 상태이고, 화면에 표시하려면 비압축 비트맵으로 디코딩해야 합니다.


### Q2. prepareForReuse에서 이미지를 nil로 설정하는 이유는? `[기본 / 빈출]`

**셀 재사용 시 이전 이미지가 잠깐 보이는 것(flickering)을 방지합니다.**

UICollectionView는 셀을 재사용합니다. 스크롤하면 화면 밖으로 나간 셀이 새 데이터로 재구성되는데, 새 이미지 로딩이 완료되기 전까지 이전 이미지가 보입니다.

또한 cancelDownloadTask()로 이전 URL의 다운로드를 취소해야 합니다. 안 그러면 이전 요청이 늦게 완료되어 잘못된 이미지가 표시될 수 있습니다.


### Q3. Downsampling을 백그라운드에서 해야 하는 이유는? `[심화 / 빈출]`

**이미지 디코딩은 CPU 집약적 작업이기 때문입니다.**

메인 스레드에서 대용량 이미지를 디코딩하면 프레임 드롭이 발생합니다. 특히 컬렉션뷰에서 빠르게 스크롤할 때 여러 이미지를 동시에 디코딩하면 16ms(60fps) 내에 처리가 안 됩니다.

해결: DispatchQueue.global()에서 downsampling 후 메인 스레드에서 UIImageView에 할당합니다. Kingfisher는 이를 자동으로 처리합니다.


---


## ✏️ 퀴즈


### 문제 1

4000x3000 RGBA 이미지의 메모리 사용량은?


   **A.** 약 12MB

   **B.** 약 24MB

✅ **C.** 약 48MB

   **D.** 약 96MB


**정답**: C


💡 **힌트**: width × height × 4bytes(RGBA) = 4000 × 3000 × 4 = 48,000,000 bytes


### 문제 2

ImageIO Downsampling에서 kCGImageSourceShouldCache: false의 역할은?


   **A.** 디스크 캐시를 비활성화한다

✅ **B.** 원본 이미지의 메모리 캐싱을 방지한다

   **C.** 썸네일 캐싱을 방지한다

   **D.** 네트워크 캐시를 비활성화한다


**정답**: B


💡 **힌트**: 원본 전체를 메모리에 캐싱하지 않아 메모리 절약 효과를 극대화합니다.


