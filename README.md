# iOS Big Tech 기술면접 — 20일 심화 복습 플랜

iOS 시니어 면접 대비를 위한 20일 학습 자료입니다.

📱 **온라인에서 바로 보기**: https://2222min.github.io/ios-interview-study/

## 📚 구성

각 Day는 다음 구조로 작성되어 있습니다:

- **📝 핵심 정리** — 주제별 깊이 있는 설명, 코드 예시, 비교표
- **💬 꼬리 질문** — 면접에서 자주 나오는 후속 질문과 1~2분 답변
- **✏️ 퀴즈** — 4지선다 문제 + 힌트

## 🗂 학습 순서

### Foundation (Day 1-5)
- [Day 1 — Value vs Reference / Copy-on-Write](days/day01.md)
- [Day 2 — ARC / 메모리 관리](days/day02.md)
- [Day 3 — Protocol Oriented Programming & Generics](days/day03.md)
- [Day 4 — Concurrency: GCD와 Swift Concurrency](days/day04.md)
- [Day 5 — RunLoop / UI 업데이트 메커니즘](days/day05.md)

### iOS Frameworks (Day 6-10)
- [Day 6 — UIKit 렌더링 파이프라인과 성능](days/day06.md)
- [Day 7 — App Lifecycle와 Scene 기반 구조](days/day07.md)
- [Day 8 — 네트워킹: URLSession과 보안](days/day08.md)
- [Day 9 — 아키텍처 패턴: MVC, MVVM, Clean Architecture](days/day09.md)
- [Day 10 — Dependency Injection과 모듈화](days/day10.md)

### Modern Swift (Day 11-15)
- [Day 11 — SwiftUI 렌더링 엔진과 상태 관리](days/day11.md)
- [Day 12 — Combine 프레임워크](days/day12.md)
- [Day 13 — Core Data](days/day13.md)
- [Day 14 — Testing](days/day14.md)
- [Day 15 — App Security](days/day15.md)

### Performance & System (Day 16-20)
- [Day 16 — Image Processing & Caching](days/day16.md)
- [Day 17 — App Launch Time 최적화](days/day17.md)
- [Day 18 — Instruments 프로파일링](days/day18.md)
- [Day 19 — Design Patterns](days/day19.md)
- [Day 20 — System Design & 면접 전략](days/day20.md)

## 🛠 콘텐츠 수정 워크플로우

1. `days/dayNN.md` 파일을 직접 수정
2. 변경 사항을 GitHub에 push
3. (선택) HTML도 업데이트하려면 `python3 build.py` 실행 → `index.html` 자동 생성
4. push하면 GitHub Pages에 자동 배포

## 📁 디렉토리 구조

```
ios-interview-study/
├── README.md           ← 이 파일
├── index.html          ← 모바일/웹용 인터랙티브 페이지
└── days/
    ├── day01.md
    ├── day02.md
    ├── ...
    └── day20.md
```
