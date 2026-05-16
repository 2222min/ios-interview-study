# Day 13 — Core Data

**태그**: NSPersistentContainer · NSManagedObjectContext · Threading · Batch Operations · SwiftData

---

## 📝 핵심 정리


### 1. NSPersistentContainer 스택 구조

_아이콘: `blue`_


### Core Data 스택이란?

Core Data의 핵심 구성 요소들의 계층 구조입니다. iOS 10부터 **NSPersistentContainer**가 이 스택을 간편하게 설정해줍니다.

### 스택 구성 요소

```swift
// Core Data Stack 계층
//
// ┌─────────────────────────────────┐
// │   NSManagedObjectContext        │  ← 작업 공간 (스크래치패드)
// ├─────────────────────────────────┤
// │   NSPersistentStoreCoordinator  │  ← 저장소 조율자
// ├─────────────────────────────────┤
// │   NSManagedObjectModel          │  ← 데이터 모델 (.xcdatamodeld)
// ├─────────────────────────────────┤
// │   NSPersistentStore (SQLite)    │  ← 실제 저장소
// └─────────────────────────────────┘
```

### NSPersistentContainer 설정

```swift
class CoreDataStack {
    static let shared = CoreDataStack()
    
    lazy var persistentContainer: NSPersistentContainer = {
        let container = NSPersistentContainer(name: "MyApp")
        
        // 마이그레이션 옵션
        let description = container.persistentStoreDescriptions.first
        description?.shouldMigrateStoreAutomatically = true
        description?.shouldInferMappingModelAutomatically = true
        
        container.loadPersistentStores { description, error in
            if let error = error {
                fatalError("Core Data 로드 실패: \\(error)")
            }
        }
        
        // viewContext 설정
        container.viewContext.automaticallyMergesChangesFromParent = true
        container.viewContext.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
        
        return container
    }()
    
    var viewContext: NSManagedObjectContext {
        persistentContainer.viewContext
    }
    
    func newBackgroundContext() -> NSManagedObjectContext {
        persistentContainer.newBackgroundContext()
    }
}
```

### 각 구성 요소의 역할

- **NSManagedObjectModel**: .xcdatamodeld 파일을 런타임 객체로 표현. Entity, Attribute, Relationship 정의

- **NSPersistentStoreCoordinator**: Model과 Store 사이의 중재자. 여러 Store를 관리 가능

- **NSPersistentStore**: 실제 데이터 저장소 (SQLite, Binary, In-Memory)

- **NSManagedObjectContext**: 객체 그래프의 작업 공간. CRUD 작업이 여기서 수행됨

> 💡 **💡 면접 포인트:** "NSPersistentContainer는 Core Data 스택 설정을 캡슐화합니다. viewContext는 메인 스레드용이고, newBackgroundContext()로 백그라운드 작업용 컨텍스트를 생성합니다. automaticallyMergesChangesFromParent를 true로 설정하면 백그라운드 변경이 자동으로 UI에 반영됩니다."


### 2. NSManagedObjectContext 스레딩 규칙

_아이콘: `green`_


### 핵심 규칙: Context는 자신의 큐에서만 접근

Core Data의 가장 중요한 규칙입니다. **NSManagedObjectContext는 생성된 큐(스레드)에서만 접근해야 합니다.** 위반 시 크래시 또는 데이터 손상이 발생합니다.

### Concurrency Type

```swift
// 두 가지 타입
let mainContext = NSManagedObjectContext(concurrencyType: .mainQueueConcurrencyType)
let bgContext = NSManagedObjectContext(concurrencyType: .privateQueueConcurrencyType)

// viewContext는 항상 mainQueueConcurrencyType
// newBackgroundContext()는 항상 privateQueueConcurrencyType
```

### perform / performAndWait

```swift
// ✅ 올바른 사용: perform 블록 안에서 접근
let bgContext = persistentContainer.newBackgroundContext()

bgContext.perform {
    // 이 블록은 bgContext의 private queue에서 실행됨
    let user = User(context: bgContext)
    user.name = "철수"
    user.age = 30
    
    do {
        try bgContext.save()
    } catch {
        print("저장 실패: \\(error)")
    }
}

// performAndWait: 동기적으로 실행 (현재 스레드 블록)
bgContext.performAndWait {
    let count = try? bgContext.count(for: fetchRequest)
}

// ❌ 잘못된 사용: perform 없이 직접 접근
DispatchQueue.global().async {
    let user = User(context: self.viewContext)  // 크래시 위험!
}
```

### Parent-Child Context 패턴

```swift
// 편집 화면에서 "취소" 기능 구현
func createEditingContext() -> NSManagedObjectContext {
    let childContext = NSManagedObjectContext(concurrencyType: .mainQueueConcurrencyType)
    childContext.parent = viewContext
    return childContext
}

// 저장: child → parent → persistent store
func saveEditing(_ context: NSManagedObjectContext) throws {
    try context.save()           // child → parent (메모리만)
    try viewContext.save()       // parent → SQLite (디스크)
}

// 취소: child를 그냥 버리면 됨 (parent에 영향 없음)
func cancelEditing(_ context: NSManagedObjectContext) {
    context.rollback()
}
```

### NSManagedObject는 Context 간 전달 불가

```swift
// ❌ 다른 context의 객체를 직접 사용
let user = fetchFromBackground(bgContext)
viewContext.perform {
    print(user.name)  // 크래시! user는 bgContext 소속
}

// ✅ objectID로 전달
let objectID = user.objectID
viewContext.perform {
    let sameUser = viewContext.object(with: objectID) as! User
    print(sameUser.name)  // 안전
}
```

> 💡 **💡 면접 답변:** "Core Data의 Context는 반드시 자신의 큐에서만 접근해야 합니다. perform/performAndWait 블록을 사용하고, 객체를 다른 Context로 전달할 때는 objectID를 사용합니다. -com.apple.CoreData.ConcurrencyDebug 1 플래그로 위반을 감지할 수 있습니다."


### 3. Batch Operations와 SwiftData 비교

_아이콘: `purple`_


### Batch Operations: 대량 데이터 처리

일반 Core Data 작업은 객체를 메모리에 로드한 후 변경합니다. 10만 건을 삭제하려면 10만 개 객체를 메모리에 올려야 하죠. **Batch Operation은 SQLite에 직접 쿼리**하여 메모리 사용 없이 처리합니다.

```swift
// Batch Delete: 메모리 로드 없이 삭제
func deleteOldRecords() {
    let fetchRequest: NSFetchRequest<NSFetchRequestResult> = Record.fetchRequest()
    fetchRequest.predicate = NSPredicate(format: "createdAt < %@", oneMonthAgo as NSDate)
    
    let batchDelete = NSBatchDeleteRequest(fetchRequest: fetchRequest)
    batchDelete.resultType = .resultTypeObjectIDs
    
    do {
        let result = try viewContext.execute(batchDelete) as? NSBatchDeleteResult
        let objectIDs = result?.result as? [NSManagedObjectID] ?? []
        
        // 중요: 메모리의 context에 변경 사항 반영
        let changes = [NSDeletedObjectsKey: objectIDs]
        NSManagedObjectContext.mergeChanges(
            fromRemoteContextSave: changes,
            into: [viewContext]
        )
    } catch {
        print("Batch delete 실패: \\(error)")
    }
}

// Batch Update: 메모리 로드 없이 업데이트
let batchUpdate = NSBatchUpdateRequest(entityName: "User")
batchUpdate.predicate = NSPredicate(format: "isActive == YES")
batchUpdate.propertiesToUpdate = ["lastSyncDate": Date()]
batchUpdate.resultType = .updatedObjectIDsResultType

// Batch Insert (iOS 13+): 대량 삽입
let batchInsert = NSBatchInsertRequest(entity: User.entity()) { (obj: NSManagedObject) -> Bool in
    guard let user = obj as? User else { return true }
    // JSON 데이터로 설정
    user.name = nextRecord.name
    return false  // false = 계속, true = 중단
}
```

### SwiftData vs Core Data 비교

| 항목 | Core Data | SwiftData |
|---|---|---|
| 모델 정의 | .xcdatamodeld (GUI) | @Model 매크로 (코드) |
| 쿼리 | NSFetchRequest + NSPredicate | #Predicate (타입 안전) |
| 스레딩 | perform 블록 필수 | @ModelActor로 간소화 |
| 최소 지원 | iOS 3+ | iOS 17+ |
| 내부 구현 | 독립 프레임워크 | Core Data 위에 구축 |

```swift
// SwiftData 예시
@Model
class User {
    var name: String
    var age: Int
    @Relationship(deleteRule: .cascade) var posts: [Post]
    
    init(name: String, age: Int) {
        self.name = name
        self.age = age
    }
}

// 쿼리 (타입 안전)
let descriptor = FetchDescriptor<User>(
    predicate: #Predicate { $0.age > 20 },
    sortBy: [SortDescriptor(\\.name)]
)
let users = try modelContext.fetch(descriptor)
```

> 💡 **💡 면접 답변:** "Batch Operation은 SQLite에 직접 쿼리하여 메모리 사용 없이 대량 데이터를 처리합니다. 단, Context의 메모리 캐시와 동기화가 필요하므로 mergeChanges를 호출해야 합니다. SwiftData는 Core Data 위에 구축된 현대적 API로, @Model 매크로와 #Predicate로 타입 안전한 코드를 작성할 수 있지만 iOS 17+ 전용입니다."


---


## 💬 꼬리 질문 (면접 답변)


### Q1. Core Data에서 백그라운드 저장 시 UI 업데이트는 어떻게 하나요? `[기본 / 빈출]`

**automaticallyMergesChangesFromParent = true**를 설정합니다.

백그라운드 Context에서 save()하면 NSPersistentStoreCoordinator를 통해 저장됩니다. viewContext에 이 옵션이 켜져 있으면 자동으로 변경 사항을 병합하여 UI가 업데이트됩니다.

또는 NotificationCenter에서 `.NSManagedObjectContextDidSave` 알림을 받아 수동으로 `mergeChanges(fromContextDidSave:)`를 호출할 수도 있습니다.


### Q2. NSFetchedResultsController의 역할은? `[기본 / 빈출]`

**Core Data 쿼리 결과를 UITableView/UICollectionView와 자동 동기화**하는 컨트롤러입니다.

데이터가 변경되면 delegate 메서드를 통해 insert/delete/update/move 이벤트를 전달합니다. 직접 fetch하고 배열 관리하는 것보다 훨씬 효율적이고, 섹션 분리도 자동으로 해줍니다.

SwiftUI에서는 @FetchRequest가 같은 역할을 합니다.


### Q3. Core Data 마이그레이션 전략은? `[심화 / 빈출]`

**두 가지 전략이 있습니다:**

1. **Lightweight Migration (자동)**: 단순 변경(속성 추가/삭제, 이름 변경)은 Core Data가 자동 처리. shouldInferMappingModelAutomatically = true

2. **Heavy Migration (수동)**: 복잡한 변경(데이터 변환, 관계 재구성)은 Mapping Model을 직접 작성. NSEntityMigrationPolicy 서브클래스로 변환 로직 구현

실무 팁: 버전별 모델을 유지하고, 점진적 마이그레이션(v1→v2→v3)으로 안정성을 확보합니다.


### Q4. Batch Delete 후 왜 mergeChanges를 호출해야 하나요? `[심화]`

**Batch Operation은 Context를 우회하여 SQLite에 직접 실행되기 때문입니다.**

일반 delete는: Context에서 삭제 → save() → SQLite 반영 → Context 캐시 자동 업데이트
Batch delete는: SQLite에 직접 DELETE 쿼리 → Context는 모름!

mergeChanges를 호출하지 않으면 Context가 이미 삭제된 객체를 여전히 가지고 있어서 fault 접근 시 크래시가 발생합니다.


---


## ✏️ 퀴즈


### 문제 1

NSManagedObjectContext의 스레딩 규칙으로 올바른 것은?


   **A.** 어떤 스레드에서든 접근 가능하다

✅ **B.** perform 블록 안에서만 접근해야 한다

   **C.** 메인 스레드에서만 접근 가능하다

   **D.** GCD로 동기화하면 된다


**정답**: B


💡 **힌트**: Context는 자신의 큐에서만 접근해야 하며, perform/performAndWait이 이를 보장합니다.


### 문제 2

SwiftData의 모델 정의 방식은?


   **A.** XML 파일로 정의

✅ **B.** @Model 매크로 사용

   **C.** NSManagedObject 상속

   **D.** Protocol 채택


**정답**: B


💡 **힌트**: SwiftData는 Swift 매크로를 활용하여 코드에서 직접 모델을 정의합니다.


