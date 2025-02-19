# Repository Content

## Sources/Atoms/AsyncPhase.swift

```
/// A value that represents a success, a failure, or a state in which the result of
/// asynchronous process has not yet been determined.
public enum AsyncPhase<Success, Failure: Error> {
    /// A suspending phase in which the result has not yet been determined.
    case suspending

    /// A success, storing a `Success` value.
    case success(Success)

    /// A failure, storing a `Failure` value.
    case failure(Failure)

    /// Creates a new phase with the given result by mapping either of a `success` or
    /// a `failure`.
    ///
    /// - Parameter result: A result value to be mapped.
    public init(_ result: Result<Success, Failure>) {
        switch result {
        case .success(let value):
            self = .success(value)

        case .failure(let error):
            self = .failure(error)
        }
    }

    #if compiler(>=6)
        /// Creates a new phase by evaluating a async throwing closure, capturing the
        /// returned value as a success, or thrown error as a failure.
        ///
        /// - Parameter body: A async throwing closure to evaluate.
        public init(
            @_inheritActorContext catching body: () async throws(Failure) -> Success
        ) async {
            do {
                let value = try await body()
                self = .success(value)
            }
            catch {
                self = .failure(error)
            }
        }
    #else
        /// Creates a new phase by evaluating a async throwing closure, capturing the
        /// returned value as a success, or thrown error as a failure.
        ///
        /// - Parameter body: A async throwing closure to evaluate.
        public init(catching body: @Sendable () async throws -> Success) async where Failure == any Error {
            do {
                let value = try await body()
                self = .success(value)
            }
            catch {
                self = .failure(error)
            }
        }
    #endif

    /// A boolean value indicating whether `self` is ``AsyncPhase/suspending``.
    public var isSuspending: Bool {
        guard case .suspending = self else {
            return false
        }

        return true
    }

    /// A boolean value indicating whether `self` is ``AsyncPhase/success(_:)``.
    public var isSuccess: Bool {
        guard case .success = self else {
            return false
        }

        return true
    }

    /// A boolean value indicating whether `self` is ``AsyncPhase/failure(_:)``.
    public var isFailure: Bool {
        guard case .failure = self else {
            return false
        }

        return true
    }

    /// Returns the success value if `self` is ``AsyncPhase/success(_:)``, otherwise returns `nil`.
    public var value: Success? {
        guard case .success(let value) = self else {
            return nil
        }

        return value
    }

    /// Returns the error value if `self` is ``AsyncPhase/failure(_:)``, otherwise returns `nil`.
    public var error: Failure? {
        guard case .failure(let error) = self else {
            return nil
        }

        return error
    }

    /// Returns a new phase, mapping any success value using the given transformation.
    ///
    /// - Parameter transform: A closure that takes the success value of this instance.
    ///
    /// - Returns: An ``AsyncPhase`` instance with the result of evaluating `transform`
    ///   as the new success value if this instance represents a success.
    public func map<NewSuccess>(_ transform: (Success) -> NewSuccess) -> AsyncPhase<NewSuccess, Failure> {
        flatMap { .success(transform($0)) }
    }

    /// Returns a new phase, mapping any failure value using the given transformation.
    ///
    /// - Parameter transform: A closure that takes the failure value of the instance.
    ///
    /// - Returns: An ``AsyncPhase`` instance with the result of evaluating `transform` as
    ///            the new failure value if this instance represents a failure.
    public func mapError<NewFailure>(_ transform: (Failure) -> NewFailure) -> AsyncPhase<Success, NewFailure> {
        flatMapError { .failure(transform($0)) }
    }

    /// Returns a new phase, mapping any success value using the given transformation
    /// and unwrapping the produced result.
    ///
    /// - Parameter transform: A closure that takes the success value of the instance.
    ///
    /// - Returns: An ``AsyncPhase`` instance, either from the closure or the previous
    ///            ``AsyncPhase/failure(_:)``.
    public func flatMap<NewSuccess>(_ transform: (Success) -> AsyncPhase<NewSuccess, Failure>) -> AsyncPhase<NewSuccess, Failure> {
        switch self {
        case .suspending:
            return .suspending

        case .success(let value):
            return transform(value)

        case .failure(let error):
            return .failure(error)
        }
    }

    /// Returns a new phase, mapping any failure value using the given transformation
    /// and unwrapping the produced result.
    ///
    /// - Parameter transform: A closure that takes the failure value of the instance.
    ///
    /// - Returns: An ``AsyncPhase`` instance, either from the closure or the previous
    ///            ``AsyncPhase/success(_:)``.
    public func flatMapError<NewFailure>(_ transform: (Failure) -> AsyncPhase<Success, NewFailure>) -> AsyncPhase<Success, NewFailure> {
        switch self {
        case .suspending:
            return .suspending

        case .success(let value):
            return .success(value)

        case .failure(let error):
            return transform(error)
        }
    }
}

extension AsyncPhase: Sendable where Success: Sendable {}
extension AsyncPhase: Equatable where Success: Equatable, Failure: Equatable {}
extension AsyncPhase: Hashable where Success: Hashable, Failure: Hashable {}

```

## Sources/Atoms/AtomStore.swift

```
/// An object that stores the state of atoms and its dependency graph.
@MainActor
public final class AtomStore {
    internal var graph = Graph()
    internal var state = StoreState()

    /// Creates a new store.
    nonisolated public init() {}
}

```

## Sources/Atoms/Snapshot.swift

````
/// A snapshot structure that captures specific set of values of atoms and their dependency graph.
public struct Snapshot: CustomStringConvertible {
    internal let graph: Graph
    internal let caches: [AtomKey: any AtomCacheProtocol]
    internal let subscriptions: [AtomKey: [SubscriberKey: Subscription]]

    internal init(
        graph: Graph,
        caches: [AtomKey: any AtomCacheProtocol],
        subscriptions: [AtomKey: [SubscriberKey: Subscription]]
    ) {
        self.graph = graph
        self.caches = caches
        self.subscriptions = subscriptions
    }

    /// A textual representation of this snapshot.
    public var description: String {
        """
        Snapshot
        - graph: \(graph)
        - caches: \(caches)
        """
    }

    /// Lookup a value associated with the given atom from the set captured in this snapshot.
    ///
    /// Note that this does not look up scoped or overridden atoms.
    ///
    /// - Parameter atom: An atom to lookup.
    ///
    /// - Returns: The captured value associated with the given atom if it exists.
    @MainActor
    public func lookup<Node: Atom>(_ atom: Node) -> Node.Produced? {
        let key = AtomKey(atom, scopeKey: nil)
        let cache = caches[key] as? AtomCache<Node>
        return cache?.value
    }

    /// Returns a DOT language representation of the dependency graph.
    ///
    /// This method generates a string that represents
    /// the [DOT the graph description language](https://graphviz.org/doc/info/lang.html)
    /// for the dependency graph of atoms clipped in this snapshot and views that use them.
    /// The generated strings can be converted into images that visually represent dependencies
    /// graph using [Graphviz](https://graphviz.org) for debugging and analysis.
    ///
    /// ## Example
    ///
    /// ```dot
    /// digraph {
    ///   node [shape=box]
    ///   "AAtom"
    ///   "AAtom" -> "BAtom"
    ///   "BAtom"
    ///   "BAtom" -> "CAtom"
    ///   "CAtom"
    ///   "CAtom" -> "Module/View.swift" [label="line:3"]
    ///   "Module/View.swift" [style=filled]
    /// }
    /// ```
    ///
    /// - Returns: A dependency graph represented in DOT the graph description language.
    public func graphDescription() -> String {
        guard !caches.keys.isEmpty else {
            return "digraph {}"
        }

        var statements = Set<String>()

        for key in caches.keys {
            statements.insert(key.description.quoted)

            if let children = graph.children[key] {
                for child in children {
                    statements.insert("\(key.description.quoted) -> \(child.description.quoted)")
                }
            }

            if let subscriptions = subscriptions[key]?.values {
                for subscription in subscriptions {
                    let label = "line:\(subscription.location.line)".quoted
                    statements.insert("\(subscription.location.fileID.quoted) [style=filled]")
                    statements.insert("\(key.description.quoted) -> \(subscription.location.fileID.quoted) [label=\(label)]")
                }
            }
        }

        return """
            digraph {
              node [shape=box]
              \(statements.sorted().joined(separator: "\n  "))
            }
            """
    }
}

private extension String {
    var quoted: String {
        "\"\(self)\""
    }
}

````

## Sources/Atoms/AtomRoot.swift

````
import SwiftUI

/// A view that stores the state of atoms.
///
/// It must be the root of any views to manage the state of atoms used throughout the application.
///
/// ```swift
/// @main
/// struct MyApp: App {
///     var body: some Scene {
///         WindowGroup {
///             AtomRoot {
///                 MyView()
///             }
///         }
///     }
/// }
/// ```
///
/// This view allows you to override a value of arbitrary atoms, which is useful
/// for dependency injection in testing.
///
/// ```swift
/// AtomRoot {
///     RootView()
/// }
/// .override(APIClientAtom()) {
///     StubAPIClient()
/// }
/// ```
///
/// You can also observe updates with a snapshot that captures a specific set of values of atoms.
///
/// ```swift
/// AtomRoot {
///     MyView()
/// }
/// .observe { snapshot in
///     if let count = snapshot.lookup(CounterAtom()) {
///         print(count)
///     }
/// }
/// ```
///
/// Additionally, if for some reason you want to manage the store on your own,
/// you can pass the instance to allow descendant views to store atom values
/// in the given store.
///
/// ```swift
/// let store = AtomStore()
///
/// struct Application: App {
///     var body: some Scene {
///         WindowGroup {
///             AtomRoot(storesIn: store) {
///                 RootView()
///             }
///         }
///     }
/// }
/// ```
///
public struct AtomRoot<Content: View>: View {
    private var storage: Storage
    private var overrides = [OverrideKey: any OverrideProtocol]()
    private var observers = [Observer]()
    private let content: Content

    /// Creates an atom root with the specified content that will be allowed to use atoms.
    ///
    /// - Parameter content: The descendant view content that provides context for atoms.
    public init(@ViewBuilder content: () -> Content) {
        self.storage = .managed
        self.content = content()
    }

    /// Creates a new scope with the specified content that will be allowed to use atoms by
    /// passing a store object.
    ///
    /// - Parameters:
    ///   - store: An object that stores the state of atoms.
    ///   - content: The descendant view content that provides context for atoms.
    public init(
        storesIn store: AtomStore,
        @ViewBuilder content: () -> Content
    ) {
        self.storage = .unmanaged(store: store)
        self.content = content()
    }

    /// The content and behavior of the view.
    public var body: some View {
        switch storage {
        case .managed:
            Managed(
                overrides: overrides,
                observers: observers,
                content: content
            )

        case .unmanaged(let store):
            Unmanaged(
                store: store,
                overrides: overrides,
                observers: observers,
                content: content
            )
        }
    }

    /// Observes the state changes with a snapshot that captures the whole atom states and
    /// their dependency graph at the point in time for debugging purposes.
    ///
    /// - Parameter onUpdate: A closure to handle a snapshot of recent updates.
    ///
    /// - Returns: The self instance.
    public func observe(_ onUpdate: @escaping @MainActor @Sendable (Snapshot) -> Void) -> Self {
        mutating(self) { $0.observers.append(Observer(onUpdate: onUpdate)) }
    }

    /// Overrides the atoms with the given value.
    ///
    /// It will create and return the given value instead of the actual atom value when accessing
    /// the overridden atom in any scopes.
    ///
    /// - Parameters:
    ///   - atom: An atom to be overridden.
    ///   - value: A value to be used instead of the atom's value.
    ///
    /// - Returns: The self instance.
    public func override<Node: Atom>(_ atom: Node, with value: @escaping @MainActor @Sendable (Node) -> Node.Produced) -> Self {
        mutating(self) { $0.overrides[OverrideKey(atom)] = Override(isScoped: false, getValue: value) }
    }

    /// Overrides the atoms with the given value.
    ///
    /// It will create and return the given value instead of the actual atom value when accessing
    /// the overridden atom in any scopes.
    /// This method overrides any atoms that has the same metatype, instead of overriding
    /// the particular instance of atom.
    ///
    /// - Parameters:
    ///   - atomType: An atom type to be overridden.
    ///   - value: A value to be used instead of the atom's value.
    ///
    /// - Returns: The self instance.
    public func override<Node: Atom>(_ atomType: Node.Type, with value: @escaping @MainActor @Sendable (Node) -> Node.Produced) -> Self {
        mutating(self) { $0.overrides[OverrideKey(atomType)] = Override(isScoped: false, getValue: value) }
    }
}

private extension AtomRoot {
    enum Storage {
        case managed
        case unmanaged(store: AtomStore)
    }

    struct Managed: View {
        let overrides: [OverrideKey: any OverrideProtocol]
        let observers: [Observer]
        let content: Content

        @State
        private var store = AtomStore()
        @State
        private var token = ScopeKey.Token()

        var body: some View {
            content.environment(
                \.store,
                StoreContext(
                    store: store,
                    scopeKey: ScopeKey(token: token),
                    inheritedScopeKeys: [:],
                    observers: observers,
                    scopedObservers: [],
                    overrides: overrides,
                    scopedOverrides: [:]
                )
            )
        }
    }

    struct Unmanaged: View {
        let store: AtomStore
        let overrides: [OverrideKey: any OverrideProtocol]
        let observers: [Observer]
        let content: Content

        @State
        private var token = ScopeKey.Token()

        var body: some View {
            content.environment(
                \.store,
                StoreContext(
                    store: store,
                    scopeKey: ScopeKey(token: token),
                    inheritedScopeKeys: [:],
                    observers: observers,
                    scopedObservers: [],
                    overrides: overrides,
                    scopedOverrides: [:]
                )
            )
        }
    }
}

````

## Sources/Atoms/AtomScope.swift

````
import SwiftUI

/// A view to override or monitor atoms in scope.
///
/// This view allows you to override a value of arbitrary atoms used in this scope, which is useful
/// for dependency injection in testing.
///
/// ```swift
/// AtomScope {
///     MyView()
/// }
/// .scopedOverride(APIClientAtom()) {
///     StubAPIClient()
/// }
/// ```
///
/// You can also observe updates with a snapshot that captures a specific set of values of atoms.
///
/// ```swift
/// AtomScope {
///     CounterView()
/// }
/// .scopedObserve { snapshot in
///     if let count = snapshot.lookup(CounterAtom()) {
///         print(count)
///     }
/// }
/// ```
///
/// It inherits from the atom store provided by ``AtomRoot`` through environment values by default,
/// but sometimes SwiftUI can fail to pass environment values in the view-tree for some reason.
/// The typical example is that, in case you use SwiftUI view inside UIKit view, it could fail as
/// SwiftUI can't pass environment values to UIKit across boundaries.
/// In that case, you can wrap the view with ``AtomScope`` and pass a view context to it so that
/// the descendant views can explicitly inherit the store.
///
/// ```swift
/// @ViewContext
/// var context
///
/// var body: some View {
///     MyUIViewWrappingView {
///         AtomScope(inheriting: context) {
///             MySwiftUIView()
///         }
///     }
/// }
/// ```
///
public struct AtomScope<Content: View>: View {
    private let inheritance: Inheritance
    private var overrides: [OverrideKey: any OverrideProtocol]
    private var observers: [Observer]
    private let content: Content

    /// Creates a new scope with the specified content.
    ///
    /// - Parameters:
    ///   - id: An identifier represents this scope used for matching with scoped atoms.
    ///   - content: The descendant view content that provides scoped context for atoms.
    public init<ID: Hashable>(id: ID = DefaultScopeID(), @ViewBuilder content: () -> Content) {
        let id = ScopeID(id)
        self.inheritance = .environment(id: id)
        self.overrides = [:]
        self.observers = []
        self.content = content()
    }

    /// Creates a new scope with the specified content that will be allowed to use atoms by
    /// passing a view context to explicitly make the descendant views inherit store.
    ///
    /// - Parameters:
    ///   - context: The parent view context that for inheriting store explicitly.
    ///   - content: The descendant view content that provides scoped context for atoms.
    public init(
        inheriting context: AtomViewContext,
        @ViewBuilder content: () -> Content
    ) {
        let store = context._store
        self.inheritance = .context(store: store)
        self.overrides = store.scopedOverrides
        self.observers = store.scopedObservers
        self.content = content()
    }

    /// The content and behavior of the view.
    public var body: some View {
        switch inheritance {
        case .environment(let id):
            WithEnvironment(
                id: id,
                overrides: overrides,
                observers: observers,
                content: content
            )

        case .context(let store):
            WithContext(
                store: store,
                overrides: overrides,
                observers: observers,
                content: content
            )
        }
    }

    /// Observes the state changes with a snapshot that captures the whole atom states and
    /// their dependency graph at the point in time for debugging purposes.
    ///
    /// Note that unlike ``AtomRoot/observe(_:)``, this observes only the state changes caused by atoms
    /// used in this scope.
    ///
    /// - Parameter onUpdate: A closure to handle a snapshot of recent updates.
    ///
    /// - Returns: The self instance.
    public func scopedObserve(_ onUpdate: @escaping @MainActor @Sendable (Snapshot) -> Void) -> Self {
        mutating(self) { $0.observers.append(Observer(onUpdate: onUpdate)) }
    }

    /// Override the atoms used in this scope with the given value.
    ///
    /// It will create and return the given value instead of the actual atom value when accessing
    /// the overridden atom in this scope.
    ///
    /// This only overrides atoms used in this scope and never be inherited to a nested scopes.
    ///
    /// - Parameters:
    ///   - atom: An atom to be overridden.
    ///   - value: A value to be used instead of the atom's value.
    ///
    /// - Returns: The self instance.
    public func scopedOverride<Node: Atom>(_ atom: Node, with value: @escaping @MainActor @Sendable (Node) -> Node.Produced) -> Self {
        mutating(self) { $0.overrides[OverrideKey(atom)] = Override(isScoped: true, getValue: value) }
    }

    /// Override the atoms used in this scope with the given value.
    ///
    /// It will create and return the given value instead of the actual atom value when accessing
    /// the overridden atom in this scope.
    /// This method overrides any atoms that has the same metatype, instead of overriding
    /// the particular instance of atom.
    ///
    /// This only overrides atoms used in this scope and never be inherited to a nested scopes.
    ///
    /// - Parameters:
    ///   - atomType: An atom type to be overridden.
    ///   - value: A value to be used instead of the atom's value.
    ///
    /// - Returns: The self instance.
    public func scopedOverride<Node: Atom>(_ atomType: Node.Type, with value: @escaping @MainActor @Sendable (Node) -> Node.Produced) -> Self {
        mutating(self) { $0.overrides[OverrideKey(atomType)] = Override(isScoped: true, getValue: value) }
    }
}

private extension AtomScope {
    enum Inheritance {
        case environment(id: ScopeID)
        case context(store: StoreContext)
    }

    struct WithEnvironment: View {
        let id: ScopeID
        let overrides: [OverrideKey: any OverrideProtocol]
        let observers: [Observer]
        let content: Content

        @State
        private var token = ScopeKey.Token()
        @Environment(\.store)
        private var environmentStore

        var body: some View {
            content.environment(
                \.store,
                environmentStore?.scoped(
                    scopeKey: ScopeKey(token: token),
                    scopeID: id,
                    observers: observers,
                    overrides: overrides
                )
            )
        }
    }

    struct WithContext: View {
        let store: StoreContext
        let overrides: [OverrideKey: any OverrideProtocol]
        let observers: [Observer]
        let content: Content

        var body: some View {
            content.environment(
                \.store,
                store.inherited(
                    scopedObservers: observers,
                    scopedOverrides: overrides
                )
            )
        }
    }
}

````

## Sources/Atoms/Suspense.swift

````
import SwiftUI

/// A view that lets the content wait for the given task to provide a resulting value
/// or an error.
///
/// ``Suspense`` manages the given task internally until the task instance is changed.
/// While the specified task is in process to provide a resulting value, it displays the
/// `suspending` content that is empty by default.
/// When the task eventually provides a resulting value, it updates the view to display
/// the given content. If the task fails, it falls back to show the `catch` content that
/// is also empty as default.
///
/// ## Example
///
/// ```swift
/// let fetchImageTask: Task<UIImage, any Error> = ...
///
/// Suspense(fetchImageTask) { uiImage in
///     // Displays content when the task successfully provides a value.
///     Image(uiImage: uiImage)
/// } suspending: {
///     // Optionally displays a suspending content.
///     ProgressView()
/// } catch: { error in
///     // Optionally displays a failure content.
///     Text(error.localizedDescription)
/// }
/// ```
///
public struct Suspense<Value: Sendable, Failure: Error, Content: View, Suspending: View, FailureContent: View>: View {
    private let task: Task<Value, Failure>
    private let content: (Value) -> Content
    private let suspending: () -> Suspending
    private let failureContent: (Failure) -> FailureContent

    @StateObject
    private var state = State()

    /// Waits for the given task to provide a resulting value and display the content
    /// accordingly.
    ///
    /// ```swift
    /// let fetchImageTask: Task<UIImage, any Error> = ...
    ///
    /// Suspense(fetchImageTask) { uiImage in
    ///     Image(uiImage: uiImage)
    /// } suspending: {
    ///     ProgressView()
    /// } catch: { error in
    ///     Text(error.localizedDescription)
    /// }
    /// ```
    ///
    /// - Parameters:
    ///   - task: A task that provides a resulting value to be displayed.
    ///   - content: A content that displays when the task successfully provides a value.
    ///   - suspending: A suspending content that displays while the task is in process.
    ///   - catch: A failure content that displays if the task fails.
    public init(
        _ task: Task<Value, Failure>,
        @ViewBuilder content: @escaping (Value) -> Content,
        @ViewBuilder suspending: @escaping () -> Suspending,
        @ViewBuilder catch: @escaping (Failure) -> FailureContent
    ) {
        self.task = task
        self.content = content
        self.suspending = suspending
        self.failureContent = `catch`
    }

    /// Waits for the given task to provide a resulting value and display the content
    /// accordingly.
    ///
    /// ```swift
    /// let fetchImageTask: Task<UIImage, any Error> = ...
    ///
    /// Suspense(fetchImageTask) { uiImage in
    ///     Image(uiImage: uiImage)
    /// }
    /// ```
    ///
    /// - Parameters:
    ///   - task: A task that provides a resulting value to be displayed.
    ///   - content: A content that displays when the task successfully provides a value.
    public init(
        _ task: Task<Value, Failure>,
        @ViewBuilder content: @escaping (Value) -> Content
    ) where Suspending == EmptyView, FailureContent == EmptyView {
        self.init(
            task,
            content: content,
            suspending: EmptyView.init,
            catch: { _ in EmptyView() }
        )
    }

    /// Waits for the given task to provide a resulting value and display the content
    /// accordingly.
    ///
    /// ```swift
    /// let fetchImageTask: Task<UIImage, any Error> = ...
    ///
    /// Suspense(fetchImageTask) { uiImage in
    ///     Image(uiImage: uiImage)
    /// } suspending: {
    ///     ProgressView()
    /// }
    /// ```
    ///
    /// - Parameters:
    ///   - task: A task that provides a resulting value to be displayed.
    ///   - content: A content that displays when the task successfully provides a value.
    ///   - suspending: A suspending content that displays while the task is in process.
    public init(
        _ task: Task<Value, Failure>,
        @ViewBuilder content: @escaping (Value) -> Content,
        @ViewBuilder suspending: @escaping () -> Suspending
    ) where FailureContent == EmptyView {
        self.init(
            task,
            content: content,
            suspending: suspending,
            catch: { _ in EmptyView() }
        )
    }

    /// Waits for the given task to provide a resulting value and display the content
    /// accordingly.
    ///
    /// ```swift
    /// let fetchImageTask: Task<UIImage, any Error> = ...
    ///
    /// Suspense(fetchImageTask) { uiImage in
    ///     Image(uiImage: uiImage)
    /// } catch: { error in
    ///     Text(error.localizedDescription)
    /// }
    /// ```
    ///
    /// - Parameters:
    ///   - task: A task that provides a resulting value to be displayed.
    ///   - content: A content that displays when the task successfully provides a value.
    ///   - catch: A failure content that displays if the task fails.
    public init(
        _ task: Task<Value, Failure>,
        @ViewBuilder content: @escaping (Value) -> Content,
        @ViewBuilder catch: @escaping (Failure) -> FailureContent
    ) where Suspending == EmptyView {
        self.init(
            task,
            content: content,
            suspending: EmptyView.init,
            catch: `catch`
        )
    }

    /// The content and behavior of the view.
    public var body: some View {
        state.task = task

        return Group {
            switch state.phase {
            case .success(let value):
                content(value)

            case .suspending:
                suspending()

            case .failure(let error):
                failureContent(error)
            }
        }
    }
}

private extension Suspense {
    @MainActor
    final class State: ObservableObject {
        @Published
        private(set) var phase = AsyncPhase<Value, Failure>.suspending

        private var suspensionTask: Task<Void, Never>? {
            didSet { oldValue?.cancel() }
        }

        var task: Task<Value, Failure>? {
            didSet {
                guard task != oldValue else {
                    return
                }

                guard let task else {
                    phase = .suspending
                    return suspensionTask = nil
                }

                suspensionTask = Task { [weak self] in
                    self?.phase = .suspending

                    let result = await task.result

                    if !Task.isCancelled {
                        self?.phase = AsyncPhase(result)
                    }
                }
            }
        }

        #if !compiler(>=6) && hasFeature(DisableOutwardActorInference)
            nonisolated init() {}
        #endif

        deinit {
            suspensionTask?.cancel()
        }
    }
}

````

## Sources/Atoms/Context/AtomTestContext.swift

````
@preconcurrency import Combine

/// A context structure to read, watch, and otherwise interact with atoms in testing.
///
/// This context has a store that manages the state of atoms, so it can be used to test individual
/// atoms or their interactions with other atoms without depending on the SwiftUI view tree.
/// Furthermore, unlike other contexts, it is possible to override atoms through this context.
@MainActor
public struct AtomTestContext: AtomWatchableContext {
    private let location: SourceLocation

    @usableFromInline
    internal let _state = State()

    /// Creates a new test context instance with a fresh internal state.
    public init(fileID: String = #fileID, line: UInt = #line) {
        location = SourceLocation(fileID: fileID, line: line)
    }

    /// A callback to perform when any of the atoms watched by this context is updated.
    @inlinable
    public var onUpdate: (() -> Void)? {
        get { _state.onUpdate }
        nonmutating set { _state.onUpdate = newValue }
    }

    /// Waits until any of the atoms watched through this context have been updated up to the
    /// specified timeout, and then returns a boolean value indicating whether an update has happened.
    ///
    /// ```swift
    /// func testAsyncUpdate() async {
    ///     let context = AtomTestContext()
    ///
    ///     let initialPhase = context.watch(AsyncCalculationAtom().phase)
    ///     XCTAssertEqual(initialPhase, .suspending)
    ///
    ///     let didUpdate = await context.waitForUpdate()
    ///     let currentPhase = context.watch(AsyncCalculationAtom().phase)
    ///
    ///     XCTAssertTure(didUpdate)
    ///     XCTAssertEqual(currentPhase, .success(123))
    /// }
    /// ```
    ///
    /// - Parameter duration: The maximum duration that this function can wait until
    ///                       the next update. The default timeout interval is `nil`
    ///                       which indicates no timeout.
    /// - Returns: A boolean value indicating whether an update has happened.
    @inlinable
    @discardableResult
    public func waitForUpdate(timeout duration: Double? = nil) async -> Bool {
        await withTaskGroup(of: Bool.self) { group in
            let updates = _state.makeUpdateStream()

            group.addTask { @MainActor @Sendable in
                for await _ in updates {
                    return true
                }
                return false
            }

            if let duration {
                group.addTask {
                    try? await Task.sleep(seconds: duration)
                    return false
                }
            }

            for await didUpdate in group {
                group.cancelAll()
                return didUpdate
            }

            return false
        }
    }

    /// Waits for the given atom until it will be in a certain state within a specified timeout,
    /// and then returns a boolean value indicating whether an update has happened.
    ///
    /// ```swift
    /// func testAsyncUpdate() async {
    ///     let context = AtomTestContext()
    ///
    ///     let initialPhase = context.watch(AsyncCalculationAtom().phase)
    ///     XCTAssertEqual(initialPhase, .suspending)
    ///
    ///     let didUpdate = await context.wait(for: AsyncCalculationAtom().phase, until: \.isSuccess)
    ///     let currentPhase = context.watch(AsyncCalculationAtom().phase)
    ///
    ///     XCTAssertTure(didUpdate)
    ///     XCTAssertEqual(currentPhase, .success(123))
    /// }
    /// ```
    ///
    /// - Parameters:
    ///   - atom: An atom expecting an update to a certain state.
    ///   - duration: The maximum duration that this function can wait until
    ///               the next update. The default timeout interval is `nil`
    ///               which indicates no timeout.
    ///   - predicate: A predicate that determines when to stop waiting.
    ///
    /// - Returns: A boolean value indicating whether an update is done.
    ///
    @inlinable
    @discardableResult
    public func wait<Node: Atom>(
        for atom: Node,
        timeout duration: Double? = nil,
        until predicate: @escaping (Node.Produced) -> Bool
    ) async -> Bool {
        await withTaskGroup(of: Bool.self) { group in
            @MainActor
            func check() -> Bool {
                guard let value = lookup(atom) else {
                    return false
                }

                return predicate(value)
            }

            let updates = _state.makeUpdateStream()

            group.addTask { @MainActor @Sendable in
                guard !check() else {
                    return false
                }

                for await _ in updates {
                    if check() {
                        return true
                    }
                }

                return false
            }

            if let duration {
                group.addTask {
                    try? await Task.sleep(seconds: duration)
                    return false
                }
            }

            for await didUpdate in group {
                group.cancelAll()
                return didUpdate
            }

            return false
        }
    }

    /// Accesses the value associated with the given atom without watching it.
    ///
    /// This method returns a value for the given atom. Accessing the atom value with this method
    /// does not initiate watching the atom, so if none of the other atoms or views are watching,
    /// the value will not be cached.
    ///
    /// ```swift
    /// let context = AtomTestContext()
    /// print(context.read(TextAtom()))  // Prints the current value associated with `TextAtom`.
    /// ```
    ///
    /// - Parameter atom: An atom to read.
    ///
    /// - Returns: The value associated with the given atom.
    @inlinable
    public func read<Node: Atom>(_ atom: Node) -> Node.Produced {
        _store.read(atom)
    }

    /// Sets the new value for the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you assign a new value, it immediately notifies downstream atoms and views.
    ///
    /// - SeeAlso: ``AtomContext/subscript(_:)``
    ///
    /// ```swift
    /// let context = AtomTestContext()
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context.set("New text", for: TextAtom())
    /// print(context.read(TextAtom()))  // Prints "New text"
    /// ```
    ///
    /// - Parameters:
    ///   - value: A value to be set.
    ///   - atom: A writable atom to update.
    @inlinable
    public func set<Node: StateAtom>(_ value: Node.Produced, for atom: Node) {
        _store.set(value, for: atom)
    }

    /// Modifies the cached value of the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you modify the value, it notifies downstream atoms and views after all
    /// modifications are completed.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context.modify(TextAtom()) { text in
    ///     text.append(" modified")
    /// }
    /// print(context.read(TextAtom()))  // Prints "Text modified"
    /// ```
    ///
    /// - Parameters:
    ///   - atom: A writable atom to modify.
    ///   - body: A value modification body.
    @inlinable
    public func modify<Node: StateAtom>(_ atom: Node, body: (inout Node.Produced) -> Void) {
        _store.modify(atom, body: body)
    }

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method accepts only asynchronous atoms such as types conforming to:
    /// ``TaskAtom``, ``ThrowingTaskAtom``, ``AsyncSequenceAtom``, ``PublisherAtom``.
    /// It refreshes the value for the given atom and then returns, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = AtomTestContext()
    /// let image = await context.refresh(AsyncImageDataAtom()).value
    /// print(image) // Prints the data obtained through the network.
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @inlinable
    @_disfavoredOverload
    @discardableResult
    public func refresh<Node: AsyncAtom>(_ atom: Node) async -> Node.Produced {
        await _store.refresh(atom)
    }

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method only accepts atoms that conform to ``Refreshable`` protocol.
    /// It refreshes the value with the custom refresh behavior, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = AtomTestContext()
    /// let value = await context.refresh(CustomRefreshableAtom())
    /// print(value)
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @inlinable
    @discardableResult
    public func refresh<Node: Refreshable>(_ atom: Node) async -> Node.Produced {
        await _store.refresh(atom)
    }

    /// Resets the value associated with the given atom, and then notifies.
    ///
    /// This method resets the value for the given atom and then notifies downstream
    /// atoms and views. Thereafter, if any other atoms or views are watching the atom, a newly
    /// generated value will be produced.
    ///
    /// ```swift
    /// let context = AtomTestContext()
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context[TextAtom()] = "New text"
    /// print(context.read(TextAtom())) // Prints "New text"
    /// context.reset(TextAtom())
    /// print(context.read(TextAtom())) // Prints "Text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    @inlinable
    @_disfavoredOverload
    public func reset<Node: Atom>(_ atom: Node) {
        _store.reset(atom)
    }

    /// Calls arbitrary reset function of the given atom.
    ///
    /// This method only accepts atoms that conform to ``Resettable`` protocol.
    /// Calls custom reset function of the given atom. Hence, it does not generate any new cache value or notify subscribers.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(ResettableTextAtom()) // Prints "Text"
    /// context[ResettableTextAtom()] = "New text"
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// context.reset(ResettableTextAtom()) // Calls the custom reset function
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    @inlinable
    public func reset<Node: Resettable>(_ atom: Node) {
        _store.reset(atom)
    }

    /// Accesses the value associated with the given atom for reading and initiates watch to
    /// receive its updates.
    ///
    /// This method returns a value for the given atom and initiates watching the atom so that
    /// the current context gets updated when the atom notifies updates.
    /// The value associated with the atom is cached until it is no longer watched or until
    /// it is updated with a new value.
    ///
    /// ```swift
    /// let context = AtomTestContext()
    /// let text = context.watch(TextAtom())
    /// print(text) // Prints the current value associated with `TextAtom`.
    /// ```
    ///
    /// - Parameter atom: An atom to watch.
    ///
    /// - Returns: The value associated with the given atom.
    @inlinable
    @discardableResult
    public func watch<Node: Atom>(_ atom: Node) -> Node.Produced {
        _store.watch(
            atom,
            subscriber: _subscriber,
            subscription: _subscription
        )
    }

    /// Returns the already cached value associated with a given atom without side effects.
    ///
    /// This method returns the value only when it is already cached, otherwise, it returns `nil`.
    /// It has no side effects such as the creation of new values or watching atoms.
    ///
    /// ```swift
    /// let context = AtomTestContext()
    /// if let text = context.lookup(TextAtom()) {
    ///     print(text)  // Prints the cached value associated with `TextAtom`.
    /// }
    /// ```
    ///
    /// - Parameter atom: An atom to lookup.
    ///
    /// - Returns: The already cached value associated with the given atom.
    @inlinable
    public func lookup<Node: Atom>(_ atom: Node) -> Node.Produced? {
        _store.lookup(atom)
    }

    /// Unwatches the given atom and do not receive any more updates of it.
    ///
    /// It simulates cases where other atoms or views no longer watches to the atom.
    ///
    /// - Parameter atom: An atom to unwatch.
    @inlinable
    public func unwatch(_ atom: some Atom) {
        _store.unwatch(atom, subscriber: _subscriber)
    }

    /// Overrides the atom value with the given value.
    ///
    /// When accessing the overridden atom, this context will create and return the given value
    /// instead of the atom value.
    ///
    /// - Parameters:
    ///   - atom: An atom to be overridden.
    ///   - value: A value to be used instead of the atom's value.
    @inlinable
    public func override<Node: Atom>(_ atom: Node, with value: @escaping @MainActor @Sendable (Node) -> Node.Produced) {
        _state.overrides[OverrideKey(atom)] = Override(isScoped: false, getValue: value)
    }

    /// Overrides the atom value with the given value.
    ///
    /// Instead of overriding the particular instance of atom, this method overrides any atom that
    /// has the same metatype.
    /// When accessing the overridden atom, this context will create and return the given value
    /// instead of the atom value.
    ///
    /// - Parameters:
    ///   - atomType: An atom type to be overridden.
    ///   - value: A value to be used instead of the atom's value.
    @inlinable
    public func override<Node: Atom>(_ atomType: Node.Type, with value: @escaping @MainActor @Sendable (Node) -> Node.Produced) {
        _state.overrides[OverrideKey(atomType)] = Override(isScoped: false, getValue: value)
    }
}

internal extension AtomTestContext {
    @usableFromInline
    @MainActor
    final class State {
        @usableFromInline
        let store = AtomStore()
        let token = ScopeKey.Token()
        let subscriberState = SubscriberState()

        @usableFromInline
        var overrides = [OverrideKey: any OverrideProtocol]()

        @usableFromInline
        var onUpdate: (() -> Void)?

        private let notifier = PassthroughSubject<Void, Never>()

        @usableFromInline
        func makeUpdateStream() -> AsyncStream<Void> {
            AsyncStream { continuation in
                let cancellable = notifier.sink(
                    receiveCompletion: { _ in
                        continuation.finish()
                    },
                    receiveValue: {
                        continuation.yield()
                    }
                )

                continuation.onTermination = { termination in
                    if case .cancelled = termination {
                        cancellable.cancel()
                    }
                }
            }
        }

        @usableFromInline
        func update() {
            onUpdate?()
            notifier.send()
        }
    }

    @usableFromInline
    var _store: StoreContext {
        StoreContext(
            store: _state.store,
            scopeKey: ScopeKey(token: _state.token),
            inheritedScopeKeys: [:],
            observers: [],
            scopedObservers: [],
            overrides: _state.overrides,
            scopedOverrides: [:]
        )
    }

    @usableFromInline
    var _subscriber: Subscriber {
        Subscriber(_state.subscriberState)
    }

    @usableFromInline
    var _subscription: Subscription {
        Subscription(location: location) { [weak _state] in
            _state?.update()
        }
    }
}

````

## Sources/Atoms/Context/AtomTransactionContext.swift

````
/// A context structure to read, watch, and otherwise interact with atoms.
///
/// When an atom is watched through this context, and that atom is updated,
/// the value of the atom where this context is provided will be updated transitively.
@MainActor
public struct AtomTransactionContext: AtomWatchableContext {
    @usableFromInline
    internal let _store: StoreContext
    @usableFromInline
    internal let _transactionState: TransactionState

    internal init(
        store: StoreContext,
        transactionState: TransactionState
    ) {
        self._store = store
        self._transactionState = transactionState
    }

    /// Accesses the value associated with the given atom without watching it.
    ///
    /// This method returns a value for the given atom. Accessing the atom value with this method
    /// does not initiate watching the atom, so if none of the other atoms or views are watching,
    /// the value will not be cached.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.read(TextAtom()))  // Prints the current value associated with `TextAtom`.
    /// ```
    ///
    /// - Parameter atom: An atom to read.
    ///
    /// - Returns: The value associated with the given atom.
    @inlinable
    public func read<Node: Atom>(_ atom: Node) -> Node.Produced {
        _store.read(atom)
    }

    /// Sets the new value for the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you assign a new value, it immediately notifies downstream atoms and views.
    ///
    /// - SeeAlso: ``AtomContext/subscript(_:)``
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context.set("New text", for: TextAtom())
    /// print(context.read(TextAtom()))  // Prints "New text"
    /// ```
    ///
    /// - Parameters:
    ///   - value: A value to be set.
    ///   - atom: A writable atom to update.
    @inlinable
    public func set<Node: StateAtom>(_ value: Node.Produced, for atom: Node) {
        _store.set(value, for: atom)
    }

    /// Modifies the cached value of the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you modify the value, it notifies downstream atoms and views after all
    /// modifications are completed.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context.modify(TextAtom()) { text in
    ///     text.append(" modified")
    /// }
    /// print(context.read(TextAtom()))  // Prints "Text modified"
    /// ```
    ///
    /// - Parameters:
    ///   - atom: A writable atom to modify.
    ///   - body: A value modification body.
    @inlinable
    public func modify<Node: StateAtom>(_ atom: Node, body: (inout Node.Produced) -> Void) {
        _store.modify(atom, body: body)
    }

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method accepts only asynchronous atoms such as types conforming to:
    /// ``TaskAtom``, ``ThrowingTaskAtom``, ``AsyncSequenceAtom``, ``PublisherAtom``.
    /// It refreshes the value for the given atom and then returns, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = ...
    /// let image = await context.refresh(AsyncImageDataAtom()).value
    /// print(image) // Prints the data obtained through the network.
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @inlinable
    @_disfavoredOverload
    @discardableResult
    public func refresh<Node: AsyncAtom>(_ atom: Node) async -> Node.Produced {
        await _store.refresh(atom)
    }

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method only accepts atoms that conform to ``Refreshable`` protocol.
    /// It refreshes the value with the custom refresh behavior, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = ...
    /// let value = await context.refresh(CustomRefreshableAtom())
    /// print(value)
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @inlinable
    @discardableResult
    public func refresh<Node: Refreshable>(_ atom: Node) async -> Node.Produced {
        await _store.refresh(atom)
    }

    /// Resets the value associated with the given atom, and then notifies.
    ///
    /// This method resets the value for the given atom and then notifies downstream
    /// atoms and views. Thereafter, if any other atoms or views are watching the atom, a newly
    /// generated value will be produced.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(ResettableTextAtom())) // Prints "Text"
    /// context[ResettableTextAtom()] = "New text"
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// context.reset(ResettableTextAtom())
    /// print(context.read(ResettableTextAtom())) // Prints "Text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    @inlinable
    @_disfavoredOverload
    public func reset<Node: Atom>(_ atom: Node) {
        _store.reset(atom)
    }

    /// Calls arbitrary reset function of the given atom.
    ///
    /// This method only accepts atoms that conform to ``Resettable`` protocol.
    /// Calls custom reset function of the given atom. Hence, it does not generate any new cache value or notify subscribers.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(ResettableTextAtom()) // Prints "Text"
    /// context[ResettableTextAtom()] = "New text"
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// context.reset(ResettableTextAtom()) // Calls the custom reset function
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    @inlinable
    public func reset<Node: Resettable>(_ atom: Node) {
        _store.reset(atom)
    }

    /// Accesses the value associated with the given atom for reading and initiates watch to
    /// receive its updates.
    ///
    /// This method returns a value for the given atom and initiates watching the atom so that
    /// the current context gets updated when the atom notifies updates.
    /// The value associated with the atom is cached until it is no longer watched or until
    /// it is updated with a new value.
    ///
    /// ```swift
    /// let context = ...
    /// let text = context.watch(TextAtom())
    /// print(text) // Prints the current value associated with `TextAtom`.
    /// ```
    ///
    /// - Parameter atom: An atom to watch.
    ///
    /// - Returns: The value associated with the given atom.
    @inlinable
    @discardableResult
    public func watch<Node: Atom>(_ atom: Node) -> Node.Produced {
        _store.watch(atom, in: _transactionState)
    }
}

````

## Sources/Atoms/Context/AtomViewContext.swift

````
import SwiftUI

/// A context structure to read, watch, and otherwise interact with atoms.
///
/// When an atom is watched through this context, and that atom is updated,
/// the view where this context is used will be rebuilt.
@MainActor
public struct AtomViewContext: AtomWatchableContext {
    @usableFromInline
    internal let _store: StoreContext
    @usableFromInline
    internal let _subscriber: Subscriber
    @usableFromInline
    internal let _subscription: Subscription

    internal init(
        store: StoreContext,
        subscriber: Subscriber,
        subscription: Subscription
    ) {
        _store = store
        _subscriber = subscriber
        _subscription = subscription
    }

    /// Accesses the value associated with the given atom without watching it.
    ///
    /// This method returns a value for the given atom. Accessing the atom value with this method
    /// does not initiate watching the atom, so if none of the other atoms or views are watching,
    /// the value will not be cached.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.read(TextAtom()))  // Prints the current value associated with `TextAtom`.
    /// ```
    ///
    /// - Parameter atom: An atom to read.
    ///
    /// - Returns: The value associated with the given atom.
    @inlinable
    public func read<Node: Atom>(_ atom: Node) -> Node.Produced {
        _store.read(atom)
    }

    /// Sets the new value for the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you assign a new value, it immediately notifies downstream atoms and views.
    ///
    /// - SeeAlso: ``AtomContext/subscript(_:)``
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context.set("New text", for: TextAtom())
    /// print(context.read(TextAtom()))  // Prints "New text"
    /// ```
    ///
    /// - Parameters:
    ///   - value: A value to be set.
    ///   - atom: A writable atom to update.
    @inlinable
    public func set<Node: StateAtom>(_ value: Node.Produced, for atom: Node) {
        _store.set(value, for: atom)
    }

    /// Modifies the cached value of the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you modify the value, it notifies downstream atoms and views after all
    /// modifications are completed.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context.modify(TextAtom()) { text in
    ///     text.append(" modified")
    /// }
    /// print(context.read(TextAtom()))  // Prints "Text modified"
    /// ```
    ///
    /// - Parameters:
    ///   - atom: A writable atom to modify.
    ///   - body: A value modification body.
    @inlinable
    public func modify<Node: StateAtom>(_ atom: Node, body: (inout Node.Produced) -> Void) {
        _store.modify(atom, body: body)
    }

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method accepts only asynchronous atoms such as types conforming to:
    /// ``TaskAtom``, ``ThrowingTaskAtom``, ``AsyncSequenceAtom``, ``PublisherAtom``.
    /// It refreshes the value for the given atom and then returns, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = ...
    /// let image = await context.refresh(AsyncImageDataAtom()).value
    /// print(image) // Prints the data obtained through the network.
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @inlinable
    @_disfavoredOverload
    @discardableResult
    public func refresh<Node: AsyncAtom>(_ atom: Node) async -> Node.Produced {
        await _store.refresh(atom)
    }

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method only accepts atoms that conform to ``Refreshable`` protocol.
    /// It refreshes the value with the custom refresh behavior, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = ...
    /// let value = await context.refresh(CustomRefreshableAtom())
    /// print(value)
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @inlinable
    @discardableResult
    public func refresh<Node: Refreshable>(_ atom: Node) async -> Node.Produced {
        await _store.refresh(atom)
    }

    /// Resets the value associated with the given atom, and then notifies.
    ///
    /// This method resets the value for the given atom and then notifies downstream
    /// atoms and views. Thereafter, if any other atoms or views are watching the atom, a newly
    /// generated value will be produced.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context[TextAtom()] = "New text"
    /// print(context.read(TextAtom())) // Prints "New text"
    /// context.reset(TextAtom())
    /// print(context.read(TextAtom())) // Prints "Text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    @inlinable
    @_disfavoredOverload
    public func reset<Node: Atom>(_ atom: Node) {
        _store.reset(atom)
    }

    /// Calls arbitrary reset function of the given atom.
    ///
    /// This method only accepts atoms that conform to ``Resettable`` protocol.
    /// Calls custom reset function of the given atom. Hence, it does not generate any new cache value or notify subscribers.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(ResettableTextAtom()) // Prints "Text"
    /// context[ResettableTextAtom()] = "New text"
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// context.reset(ResettableTextAtom()) // Calls the custom reset function
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    @inlinable
    public func reset<Node: Resettable>(_ atom: Node) {
        _store.reset(atom)
    }

    /// Accesses the value associated with the given atom for reading and initiates watch to
    /// receive its updates.
    ///
    /// This method returns a value for the given atom and initiates watching the atom so that
    /// the current context gets updated when the atom notifies updates.
    /// The value associated with the atom is cached until it is no longer watched or until
    /// it is updated with a new value.
    ///
    /// ```swift
    /// let context = ...
    /// let text = context.watch(TextAtom())
    /// print(text) // Prints the current value associated with `TextAtom`.
    /// ```
    ///
    /// - Parameter atom: An atom to watch.
    ///
    /// - Returns: The value associated with the given atom.
    @discardableResult
    @inlinable
    public func watch<Node: Atom>(_ atom: Node) -> Node.Produced {
        _store.watch(
            atom,
            subscriber: _subscriber,
            subscription: _subscription
        )
    }

    /// Creates a `Binding` that accesses the value of the given read-write atom.
    ///
    /// This method only accepts read-write atoms such as ones conforming to ``StateAtom``,
    /// and returns a binding that accesses the value or set a new value for the atom.
    /// When you set a new value to the `wrappedValue` of the returned binding, it assigns the value
    /// to the atom, and immediately notifies downstream atoms and views.
    /// Note that the binding initiates watching the given atom when the value is accessed through the
    /// `wrappedValue`.
    ///
    /// ```swift
    /// let context = ...
    /// let binding = context.binding(TextAtom())
    /// binding.wrappedValue = "New text"
    /// binding.wrappedValue.append(" is mutated!")
    /// print(binding.wrappedValue) // Prints "New text is mutated!"
    /// ```
    ///
    /// - Parameter atom: An atom to create binding to.
    ///
    /// - Returns: A binding to the atom value.
    @inlinable
    public func binding<Node: StateAtom>(_ atom: Node) -> Binding<Node.Produced> {
        Binding(
            get: { watch(atom) },
            set: { set($0, for: atom) }
        )
    }

    /// Takes a snapshot of an atom hierarchy for debugging purposes.
    ///
    /// This method captures all of the atom values and dependencies currently in use in
    /// the descendants of `AtomRoot` and returns a `Snapshot` that allows you to analyze
    /// or rollback to a specific state.
    ///
    /// - Returns: A snapshot that contains values of atoms.
    @inlinable
    public func snapshot() -> Snapshot {
        _store.snapshot()
    }

    /// Restores atom values and the dependency graph captured at a point in time in the given snapshot for debugging purposes.
    ///
    /// Any atoms and their dependencies that are no longer subscribed to will be released.
    ///
    /// - Parameter snapshot: A snapshot that contains values of atoms.
    @inlinable
    public func restore(_ snapshot: Snapshot) {
        _store.restore(snapshot)
    }
}

````

## Sources/Atoms/Context/AtomContext.swift

````
import SwiftUI

/// A context structure to read, write, and otherwise interact with atoms.
///
/// - SeeAlso: ``AtomWatchableContext``
@MainActor
public protocol AtomContext {
    /// Accesses the value associated with the given atom without watching it.
    ///
    /// This method returns a value for the given atom. Accessing the atom value with this method
    /// does not initiate watching the atom, so if none of the other atoms or views are watching,
    /// the value will not be cached.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.read(TextAtom()))  // Prints the current value associated with ``TextAtom``.
    /// ```
    ///
    /// - Parameter atom: An atom to read.
    ///
    /// - Returns: The value associated with the given atom.
    func read<Node: Atom>(_ atom: Node) -> Node.Produced

    /// Sets the new value for the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you assign a new value, it immediately notifies downstream atoms and views.
    ///
    /// - SeeAlso: ``AtomContext/subscript(_:)``
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context.set("New text", for: TextAtom())
    /// print(context.read(TextAtom()))  // Prints "New text"
    /// ```
    ///
    /// - Parameters:
    ///   - value: A value to be set.
    ///   - atom: A writable atom to update.
    func set<Node: StateAtom>(_ value: Node.Produced, for atom: Node)

    /// Modifies the cached value of the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you modify the value, it notifies downstream atoms or views after all
    /// modifications are completed.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context.modify(TextAtom()) { text in
    ///     text.append(" modified")
    /// }
    /// print(context.read(TextAtom()))  // Prints "Text modified"
    /// ```
    ///
    /// - Parameters:
    ///   - atom: A writable atom to modify.
    ///   - body: A value modification body.
    func modify<Node: StateAtom>(_ atom: Node, body: (inout Node.Produced) -> Void)

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method accepts only asynchronous atoms such as types conforming to:
    /// ``TaskAtom``, ``ThrowingTaskAtom``, ``AsyncSequenceAtom``, ``PublisherAtom``.
    /// It refreshes the value for the given atom and then returns, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = ...
    /// let image = await context.refresh(AsyncImageDataAtom()).value
    /// print(image) // Prints the data obtained through the network.
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @_disfavoredOverload
    @discardableResult
    func refresh<Node: AsyncAtom>(_ atom: Node) async -> Node.Produced

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method only accepts atoms that conform to ``Refreshable`` protocol.
    /// It refreshes the value with the custom refresh behavior, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = ...
    /// let value = await context.refresh(CustomRefreshableAtom())
    /// print(value)
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @discardableResult
    func refresh<Node: Refreshable>(_ atom: Node) async -> Node.Produced

    /// Resets the value associated with the given atom, and then notifies.
    ///
    /// This method resets the value for the given atom and then notifies downstream
    /// atoms and views. Thereafter, if any other atoms or views are watching the atom, a newly
    /// generated value will be produced.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context[TextAtom()] = "New text"
    /// print(context.read(TextAtom())) // Prints "New text"
    /// context.reset(TextAtom())
    /// print(context.read(TextAtom())) // Prints "Text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    @_disfavoredOverload
    func reset<Node: Atom>(_ atom: Node)

    /// Calls arbitrary reset function of the given atom.
    ///
    /// This method only accepts atoms that conform to ``Resettable`` protocol.
    /// Calls custom reset function of the given atom. Hence, it does not generate any new cache value or notify subscribers.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(ResettableTextAtom()) // Prints "Text"
    /// context[ResettableTextAtom()] = "New text"
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// context.reset(ResettableTextAtom()) // Calls the custom reset function
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    func reset<Node: Resettable>(_ atom: Node)
}

public extension AtomContext {
    /// Accesses the value associated with the given read-write atom for mutating.
    ///
    /// This subscript only accepts read-write atoms such as types conforming to ``StateAtom``,
    /// and returns the value or assigns a new value for the atom.
    /// When you assign a new value, it immediately notifies downstream atoms and views,
    /// but it doesn't start watching the atom.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context[TextAtom()] = "New text"
    /// context[TextAtom()].append(" is mutated!")
    /// print(context[TextAtom()])       // Prints "New text is mutated!"
    /// ```
    ///
    /// - Parameter atom: An atom to read or write.
    ///
    /// - Returns: The value associated with the given atom.
    subscript<Node: StateAtom>(_ atom: Node) -> Node.Produced {
        get { read(atom) }
        nonmutating set { set(newValue, for: atom) }
    }
}

/// A context structure to read, watch, and otherwise interact with atoms.
///
/// - SeeAlso: ``AtomViewContext``
/// - SeeAlso: ``AtomTransactionContext``
/// - SeeAlso: ``AtomTestContext``
@MainActor
public protocol AtomWatchableContext: AtomContext {
    /// Accesses the value associated with the given atom for reading and initiates watch to
    /// receive its updates.
    ///
    /// This method returns a value for the given atom and initiates watching the atom so that
    /// the current context gets updated when the atom notifies updates.
    /// The value associated with the atom is cached until it is no longer watched or until
    /// it is updated with a new value.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints the current value associated with `TextAtom`.
    /// ```
    ///
    /// - Parameter atom: An atom to watch.
    ///
    /// - Returns: The value associated with the given atom.
    @discardableResult
    func watch<Node: Atom>(_ atom: Node) -> Node.Produced
}

````

## Sources/Atoms/Context/AtomCurrentContext.swift

````
/// A context structure to read, set, and otherwise interact with atoms.
@MainActor
public struct AtomCurrentContext: AtomContext {
    @usableFromInline
    internal let _store: StoreContext

    internal init(store: StoreContext) {
        self._store = store
    }

    /// Accesses the value associated with the given atom without watching it.
    ///
    /// This method returns a value for the given atom. Accessing the atom value with this method
    /// does not initiate watching the atom, so if none of the other atoms or views are watching,
    /// the value will not be cached.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.read(TextAtom()))  // Prints the current value associated with `TextAtom`.
    /// ```
    ///
    /// - Parameter atom: An atom to read.
    ///
    /// - Returns: The value associated with the given atom.
    @inlinable
    public func read<Node: Atom>(_ atom: Node) -> Node.Produced {
        _store.read(atom)
    }

    /// Sets the new value for the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you assign a new value, it immediately notifies downstream atoms and views.
    ///
    /// - SeeAlso: ``AtomContext/subscript(_:)``
    ///
    /// ```swift
    /// let context = ...
    /// context.set("New text", for: TextAtom())
    /// print(context.read(TextAtom()))  // Prints "New text"
    /// ```
    ///
    /// - Parameters:
    ///   - value: A value to be set.
    ///   - atom: A writable atom to update.
    @inlinable
    public func set<Node: StateAtom>(_ value: Node.Produced, for atom: Node) {
        _store.set(value, for: atom)
    }

    /// Modifies the cached value of the given writable atom.
    ///
    /// This method only accepts writable atoms such as types conforming to ``StateAtom``,
    /// and assigns a new value for the atom.
    /// When you modify the value, it notifies downstream atoms and views after all
    /// modifications are completed.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(TextAtom())) // Prints "Text"
    /// context.modify(TextAtom()) { text in
    ///     text.append(" modified")
    /// }
    /// print(context.read(TextAtom()))  // Prints "Text modified"
    /// ```
    ///
    /// - Parameters:
    ///   - atom: A writable atom to modify.
    ///   - body: A value modification body.
    @inlinable
    public func modify<Node: StateAtom>(_ atom: Node, body: (inout Node.Produced) -> Void) {
        _store.modify(atom, body: body)
    }

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method accepts only asynchronous atoms such as types conforming to:
    /// ``TaskAtom``, ``ThrowingTaskAtom``, ``AsyncSequenceAtom``, ``PublisherAtom``.
    /// It refreshes the value for the given atom and then returns, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = ...
    /// let image = await context.refresh(AsyncImageDataAtom()).value
    /// print(image) // Prints the data obtained through the network.
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @inlinable
    @_disfavoredOverload
    @discardableResult
    public func refresh<Node: AsyncAtom>(_ atom: Node) async -> Node.Produced {
        await _store.refresh(atom)
    }

    /// Refreshes and then returns the value associated with the given refreshable atom.
    ///
    /// This method only accepts atoms that conform to ``Refreshable`` protocol.
    /// It refreshes the value with the custom refresh behavior, so the caller can await until
    /// the atom completes the update.
    /// Note that it can be used only in a context that supports concurrency.
    ///
    /// ```swift
    /// let context = ...
    /// let value = await context.refresh(CustomRefreshableAtom())
    /// print(value)
    /// ```
    ///
    /// - Parameter atom: An atom to refresh.
    ///
    /// - Returns: The value after the refreshing associated with the given atom is completed.
    @inlinable
    @discardableResult
    public func refresh<Node: Refreshable>(_ atom: Node) async -> Node.Produced {
        await _store.refresh(atom)
    }

    /// Resets the value associated with the given atom, and then notifies.
    ///
    /// This method resets the value for the given atom and then notifies downstream
    /// atoms and views. Thereafter, if any other atoms or views are watching the atom, a newly
    /// generated value will be produced.
    ///
    /// ```swift
    /// let context = ...
    /// context[TextAtom()] = "New text"
    /// print(context.read(TextAtom())) // Prints "New text"
    /// context.reset(TextAtom())
    /// print(context.read(TextAtom())) // Prints "Text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    @inlinable
    @_disfavoredOverload
    public func reset<Node: Atom>(_ atom: Node) {
        _store.reset(atom)
    }

    /// Calls arbitrary reset function of the given atom.
    ///
    /// This method only accepts atoms that conform to ``Resettable`` protocol.
    /// Calls custom reset function of the given atom. Hence, it does not generate any new cache value or notify subscribers.
    ///
    /// ```swift
    /// let context = ...
    /// print(context.watch(ResettableTextAtom()) // Prints "Text"
    /// context[ResettableTextAtom()] = "New text"
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// context.reset(ResettableTextAtom()) // Calls the custom reset function
    /// print(context.read(ResettableTextAtom())) // Prints "New text"
    /// ```
    ///
    /// - Parameter atom: An atom to reset.
    @inlinable
    public func reset<Node: Resettable>(_ atom: Node) {
        _store.reset(atom)
    }
}

````

## Sources/Atoms/Core/Observer.swift

```
@usableFromInline
internal struct Observer: Sendable {
    let onUpdate: @MainActor @Sendable (Snapshot) -> Void
}

```

## Sources/Atoms/Core/ScopeKey.swift

```
@usableFromInline
internal struct ScopeKey: Hashable, Sendable, CustomStringConvertible {
    final class Token {}

    private let identifier: ObjectIdentifier

    @usableFromInline
    var description: String {
        String(hashValue, radix: 36, uppercase: false)
    }

    init(token: Token) {
        identifier = ObjectIdentifier(token)
    }
}

```

## Sources/Atoms/Core/Subscriber.swift

```
@usableFromInline
@MainActor
internal struct Subscriber {
    private weak var state: SubscriberState?

    let key: SubscriberKey

    init(_ state: SubscriberState) {
        self.state = state
        self.key = SubscriberKey(token: state.token)
    }

    var subscribing: Set<AtomKey> {
        get { state?.subscribing ?? [] }
        nonmutating set { state?.subscribing = newValue }
    }

    var unsubscribe: ((Set<AtomKey>) -> Void)? {
        get { state?.unsubscribe }
        nonmutating set { state?.unsubscribe = newValue }
    }
}

```

## Sources/Atoms/Core/Utilities.swift

```
@inlinable
internal func `mutating`<T>(_ value: T, _ mutation: (inout T) -> Void) -> T {
    var value = value
    mutation(&value)
    return value
}

internal extension Task where Success == Never, Failure == Never {
    @inlinable
    static func sleep(seconds duration: Double) async throws {
        try await sleep(nanoseconds: UInt64(duration * 1_000_000_000))
    }
}

```

## Sources/Atoms/Core/AtomCache.swift

```
internal protocol AtomCacheProtocol {
    associatedtype Node: Atom

    var atom: Node { get set }
    var value: Node.Produced { get set }
}

internal struct AtomCache<Node: Atom>: AtomCacheProtocol, CustomStringConvertible {
    var atom: Node
    var value: Node.Produced

    var description: String {
        "\(value)"
    }
}

```

## Sources/Atoms/Core/Environment.swift

```
import SwiftUI

internal extension EnvironmentValues {
    var store: StoreContext? {
        get { self[StoreEnvironmentKey.self] }
        set { self[StoreEnvironmentKey.self] = newValue }
    }
}

private struct StoreEnvironmentKey: EnvironmentKey {
    static var defaultValue: StoreContext? {
        nil
    }
}

```

## Sources/Atoms/Core/StoreContext.swift

```
@usableFromInline
@MainActor
internal struct StoreContext {
    private let store: AtomStore
    private let scopeKey: ScopeKey
    private let inheritedScopeKeys: [ScopeID: ScopeKey]
    private let observers: [Observer]
    private let overrides: [OverrideKey: any OverrideProtocol]

    let scopedObservers: [Observer]
    let scopedOverrides: [OverrideKey: any OverrideProtocol]

    init(
        store: AtomStore,
        scopeKey: ScopeKey,
        inheritedScopeKeys: [ScopeID: ScopeKey],
        observers: [Observer],
        scopedObservers: [Observer],
        overrides: [OverrideKey: any OverrideProtocol],
        scopedOverrides: [OverrideKey: any OverrideProtocol]
    ) {
        self.store = store
        self.scopeKey = scopeKey
        self.inheritedScopeKeys = inheritedScopeKeys
        self.observers = observers
        self.scopedObservers = scopedObservers
        self.overrides = overrides
        self.scopedOverrides = scopedOverrides
    }

    func inherited(
        scopedObservers: [Observer],
        scopedOverrides: [OverrideKey: any OverrideProtocol]
    ) -> StoreContext {
        StoreContext(
            store: store,
            scopeKey: scopeKey,
            inheritedScopeKeys: inheritedScopeKeys,
            observers: observers,
            scopedObservers: scopedObservers,
            overrides: overrides,
            scopedOverrides: scopedOverrides
        )
    }

    func scoped(
        scopeKey: ScopeKey,
        scopeID: ScopeID,
        observers: [Observer],
        overrides: [OverrideKey: any OverrideProtocol]
    ) -> StoreContext {
        StoreContext(
            store: store,
            scopeKey: scopeKey,
            inheritedScopeKeys: mutating(inheritedScopeKeys) { $0[scopeID] = scopeKey },
            observers: self.observers,
            scopedObservers: observers,
            overrides: self.overrides,
            scopedOverrides: overrides
        )
    }

    @usableFromInline
    func read<Node: Atom>(_ atom: Node) -> Node.Produced {
        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)

        if let cache = lookupCache(of: atom, for: key) {
            return cache.value
        }
        else {
            let value = initialize(of: atom, for: key, override: override)
            checkAndRelease(for: key)
            return value
        }
    }

    @usableFromInline
    func set<Node: StateAtom>(_ value: Node.Produced, for atom: Node) {
        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)

        if let cache = lookupCache(of: atom, for: key) {
            update(atom: atom, for: key, oldValue: cache.value, newValue: value)
        }
    }

    @usableFromInline
    func modify<Node: StateAtom>(_ atom: Node, body: (inout Node.Produced) -> Void) {
        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)

        if let cache = lookupCache(of: atom, for: key) {
            let newValue = mutating(cache.value, body)
            update(atom: atom, for: key, oldValue: cache.value, newValue: newValue)
        }
    }

    @usableFromInline
    func watch<Node: Atom>(_ atom: Node, in transactionState: TransactionState) -> Node.Produced {
        guard !transactionState.isTerminated else {
            return read(atom)
        }

        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)
        let cache = lookupCache(of: atom, for: key)
        let value = cache?.value ?? initialize(of: atom, for: key, override: override)

        // Add an `Edge` from the upstream to downstream.
        store.graph.dependencies[transactionState.key, default: []].insert(key)
        store.graph.children[key, default: []].insert(transactionState.key)

        return value
    }

    @usableFromInline
    func watch<Node: Atom>(
        _ atom: Node,
        subscriber: Subscriber,
        subscription: Subscription
    ) -> Node.Produced {
        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)
        let cache = lookupCache(of: atom, for: key)
        let value = cache?.value ?? initialize(of: atom, for: key, override: override)
        let isNewSubscription = subscriber.subscribing.insert(key).inserted

        if isNewSubscription {
            store.state.subscriptions[key, default: [:]][subscriber.key] = subscription
            subscriber.unsubscribe = { keys in
                unsubscribe(keys, for: subscriber.key)
            }
            notifyUpdateToObservers()
        }

        return value
    }

    @usableFromInline
    @_disfavoredOverload
    func refresh<Node: AsyncAtom>(_ atom: Node) async -> Node.Produced {
        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)
        let context = prepareForTransaction(of: atom, for: key)
        let value: Node.Produced

        if let override {
            value = override.getValue(atom)
        }
        else {
            value = await atom.refreshProducer.getValue(context)
        }

        await atom.refreshProducer.refreshValue(value, context)

        guard let cache = lookupCache(of: atom, for: key) else {
            checkAndRelease(for: key)
            return value
        }

        // Notify update unless it's cancelled or terminated by other operations.
        if !Task.isCancelled && !context.isTerminated {
            update(atom: atom, for: key, oldValue: cache.value, newValue: value)
        }

        return value
    }

    @usableFromInline
    func refresh<Node: Refreshable>(_ atom: Node) async -> Node.Produced {
        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)
        let state = getState(of: atom, for: key)
        let context = AtomCurrentContext(store: self)

        // Detach the dependencies once to delay updating the downstream until
        // this atom's value refresh is complete.
        let dependencies = detachDependencies(for: key)
        let value = await atom.refresh(context: context)

        // Restore dependencies when the refresh is completed.
        attachDependencies(dependencies, for: key)

        guard let transactionState = state.transactionState, let cache = lookupCache(of: atom, for: key) else {
            checkAndRelease(for: key)
            return value
        }

        // Notify update unless it's cancelled or terminated by other operations.
        if !Task.isCancelled && !transactionState.isTerminated {
            update(atom: atom, for: key, oldValue: cache.value, newValue: value)
        }

        return value
    }

    @usableFromInline
    @_disfavoredOverload
    func reset<Node: Atom>(_ atom: Node) {
        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)

        if let cache = lookupCache(of: atom, for: key) {
            let newValue = getValue(of: atom, for: key, override: override)
            update(atom: atom, for: key, oldValue: cache.value, newValue: newValue)
        }
    }

    @usableFromInline
    func reset<Node: Resettable>(_ atom: Node) {
        let context = AtomCurrentContext(store: self)
        atom.reset(context: context)
    }

    @usableFromInline
    func lookup<Node: Atom>(_ atom: Node) -> Node.Produced? {
        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)
        let cache = lookupCache(of: atom, for: key)

        return cache?.value
    }

    @usableFromInline
    func unwatch(_ atom: some Atom, subscriber: Subscriber) {
        let override = lookupOverride(of: atom)
        let scopeKey = lookupScopeKey(of: atom, override: override)
        let key = AtomKey(atom, scopeKey: scopeKey)

        subscriber.subscribing.remove(key)
        unsubscribe([key], for: subscriber.key)
    }

    @usableFromInline
    func snapshot() -> Snapshot {
        Snapshot(
            graph: store.graph,
            caches: store.state.caches,
            subscriptions: store.state.subscriptions
        )
    }

    @usableFromInline
    func restore(_ snapshot: Snapshot) {
        let keys = snapshot.caches.keys
        var disusedDependencies = [AtomKey: Set<AtomKey>]()

        for key in keys {
            let oldDependencies = store.graph.dependencies[key]
            let newDependencies = snapshot.graph.dependencies[key]

            // Update atom values and the graph.
            store.state.caches[key] = snapshot.caches[key]
            store.graph.dependencies[key] = newDependencies
            store.graph.children[key] = snapshot.graph.children[key]
            disusedDependencies[key] = oldDependencies?.subtracting(newDependencies ?? [])
        }

        for key in keys {
            // Release if the atom is no longer used.
            checkAndRelease(for: key)

            // Release dependencies that are no longer dependent.
            if let dependencies = disusedDependencies[key] {
                for dependency in dependencies {
                    store.graph.children[dependency]?.remove(key)
                    checkAndRelease(for: dependency)
                }
            }

            // Notify updates only for the subscriptions of restored atoms.
            if let subscriptions = store.state.subscriptions[key] {
                for subscription in subscriptions.values {
                    subscription.update()
                }
            }
        }

        notifyUpdateToObservers()
    }
}

private extension StoreContext {
    func initialize<Node: Atom>(
        of atom: Node,
        for key: AtomKey,
        override: Override<Node>?
    ) -> Node.Produced {
        let value = getValue(of: atom, for: key, override: override)
        let state = getState(of: atom, for: key)

        store.state.caches[key] = AtomCache(atom: atom, value: value)

        let context = AtomCurrentContext(store: self)
        state.effect.initialized(context: context)

        return value
    }

    func update<Node: Atom>(
        atom: Node,
        for key: AtomKey,
        oldValue: Node.Produced,
        newValue: Node.Produced
    ) {
        store.state.caches[key] = AtomCache(atom: atom, value: newValue)

        // Check whether if the dependent atoms should be updated transitively.
        guard atom.producer.shouldUpdate(oldValue, newValue) else {
            return
        }

        // Perform side effects first.
        let state = getState(of: atom, for: key)
        let context = AtomCurrentContext(store: self)
        state.effect.updated(context: context)

        // Calculate topological order for updating downstream efficiently.
        let (edges, redundantDependencies) = store.topologicalSorted(key: key)
        var skippedDependencies = Set<AtomKey>()

        // Updates the given atom.
        func update(for key: AtomKey, cache: some AtomCacheProtocol) {
            let override = lookupOverride(of: cache.atom)
            let newValue = getValue(of: cache.atom, for: key, override: override)

            store.state.caches[key] = AtomCache(atom: cache.atom, value: newValue)

            // Check whether if the dependent atoms should be updated transitively.
            guard cache.atom.producer.shouldUpdate(cache.value, newValue) else {
                // Record the atom to avoid downstream from being update.
                skippedDependencies.insert(key)
                return
            }

            // Perform side effects before updating downstream.
            let state = getState(of: cache.atom, for: key)
            state.effect.updated(context: context)
        }

        // Performs update of the given atom with the dependency's context.
        func performUpdate(for key: AtomKey, cache: some AtomCacheProtocol, dependency: some Atom) {
            dependency.producer.performUpdate {
                update(for: key, cache: cache)
            }
        }

        // Performs update of the given subscription with the dependency's context.
        func performUpdate(subscription: Subscription, dependency: some Atom) {
            dependency.producer.performUpdate(subscription.update)
        }

        func validEdge(_ edge: Edge) -> Edge? {
            // Do not transitively update atoms that have dependency recorded not to update downstream.
            guard skippedDependencies.contains(edge.from) else {
                return edge
            }

            // If the topological sorting has marked the vertex as a redundant, the update still performed.
            guard let fromKey = redundantDependencies[edge.to]?.first(where: { !skippedDependencies.contains($0) }) else {
                return nil
            }

            // Convert edge's `from`, which represents a dependency atom, to a non-skipped one to
            // change the update transaction context (e.g. animation).
            return Edge(from: fromKey, to: edge.to)
        }

        // Perform transitive update for dependent atoms ahead of notifying updates to subscriptions.
        for edge in edges {
            switch edge.to {
            case .atom(let key):
                guard let edge = validEdge(edge) else {
                    // Record the atom to avoid downstream from being update.
                    skippedDependencies.insert(key)
                    continue
                }

                let cache = store.state.caches[key]
                let dependencyCache = store.state.caches[edge.from]

                if let cache, let dependencyCache {
                    performUpdate(for: key, cache: cache, dependency: dependencyCache.atom)
                }

            case .subscriber(let key):
                guard let edge = validEdge(edge) else {
                    continue
                }

                let subscription = store.state.subscriptions[edge.from]?[key]
                let dependencyCache = store.state.caches[edge.from]

                if let subscription, let dependencyCache {
                    performUpdate(subscription: subscription, dependency: dependencyCache.atom)
                }
            }
        }

        // Notify the observers after all updates are completed.
        notifyUpdateToObservers()
    }

    func release(for key: AtomKey) {
        let dependencies = store.graph.dependencies.removeValue(forKey: key)
        let state = store.state.states.removeValue(forKey: key)

        store.graph.children.removeValue(forKey: key)
        store.state.caches.removeValue(forKey: key)
        store.state.subscriptions.removeValue(forKey: key)

        if let dependencies {
            for dependency in dependencies {
                store.graph.children[dependency]?.remove(key)
                checkAndRelease(for: dependency)
            }
        }

        state?.transactionState?.terminate()

        let context = AtomCurrentContext(store: self)
        state?.effect.released(context: context)
    }

    func checkAndRelease(for key: AtomKey) {
        // The condition under which an atom may be released are as follows:
        //     1. It's not marked as `KeepAlive`, is marked as `Scoped`, or is scoped by override.
        //     2. It has no downstream atoms.
        //     3. It has no subscriptions from views.
        lazy var shouldKeepAlive = !key.isScoped && store.state.caches[key].map { $0.atom is any KeepAlive } ?? false
        lazy var isChildrenEmpty = store.graph.children[key]?.isEmpty ?? true
        lazy var isSubscriptionEmpty = store.state.subscriptions[key]?.isEmpty ?? true
        let shouldRelease = !shouldKeepAlive && isChildrenEmpty && isSubscriptionEmpty

        guard shouldRelease else {
            return
        }

        release(for: key)
    }

    func detachDependencies(for key: AtomKey) -> Set<AtomKey> {
        // Remove current dependencies.
        let dependencies = store.graph.dependencies.removeValue(forKey: key) ?? []

        // Detatch the atom from its children.
        for dependency in dependencies {
            store.graph.children[dependency]?.remove(key)
        }

        return dependencies
    }

    func attachDependencies(_ dependencies: Set<AtomKey>, for key: AtomKey) {
        // Set dependencies.
        store.graph.dependencies[key] = dependencies

        // Attach the atom to its children.
        for dependency in dependencies {
            store.graph.children[dependency]?.insert(key)
        }
    }

    func unsubscribe<Keys: Sequence<AtomKey>>(_ keys: Keys, for subscriberKey: SubscriberKey) {
        for key in keys {
            store.state.subscriptions[key]?.removeValue(forKey: subscriberKey)
            checkAndRelease(for: key)
        }

        notifyUpdateToObservers()
    }

    func prepareForTransaction<Node: Atom>(
        of atom: Node,
        for key: AtomKey
    ) -> AtomProducerContext<Node.Produced> {
        let transactionState = TransactionState(key: key) {
            let oldDependencies = detachDependencies(for: key)

            return {
                let dependencies = store.graph.dependencies[key] ?? []
                let disusedDependencies = oldDependencies.subtracting(dependencies)

                // Release disused dependencies if no longer used.
                for dependency in disusedDependencies {
                    checkAndRelease(for: dependency)
                }
            }
        }

        let state = getState(of: atom, for: key)
        // Terminate the ongoing transaction first.
        state.transactionState?.terminate()
        // Register the transaction state so it can be terminated from anywhere.
        state.transactionState = transactionState

        return AtomProducerContext(store: self, transactionState: transactionState) { newValue in
            if let cache = lookupCache(of: atom, for: key) {
                update(atom: atom, for: key, oldValue: cache.value, newValue: newValue)
            }
        }
    }

    func getValue<Node: Atom>(
        of atom: Node,
        for key: AtomKey,
        override: Override<Node>?
    ) -> Node.Produced {
        let context = prepareForTransaction(of: atom, for: key)
        let value: Node.Produced

        if let override {
            value = override.getValue(atom)
        }
        else {
            value = atom.producer.getValue(context)
        }

        atom.producer.manageValue(value, context)
        return value
    }

    func getState<Node: Atom>(of atom: Node, for key: AtomKey) -> AtomState<Node.Effect> {
        if let state = lookupState(of: atom, for: key) {
            return state
        }

        let context = AtomCurrentContext(store: self)
        let effect = atom.effect(context: context)
        let state = AtomState(effect: effect)
        store.state.states[key] = state
        return state
    }

    func lookupState<Node: Atom>(of atom: Node, for key: AtomKey) -> AtomState<Node.Effect>? {
        guard let baseState = store.state.states[key] else {
            return nil
        }

        guard let state = baseState as? AtomState<Node.Effect> else {
            assertionFailure(
                """
                [Atoms]
                The type of the given atom's value and the state did not match.
                There might be duplicate keys, make sure that the keys for all atom types are unique.

                Atom: \(Node.self)
                Key: \(type(of: atom.key))
                Detected: \(type(of: baseState))
                Expected: AtomState<\(Node.Effect.self)>
                """
            )

            // Release the invalid registration as a fallback.
            release(for: key)
            return nil
        }

        return state
    }

    func lookupCache<Node: Atom>(of atom: Node, for key: AtomKey) -> AtomCache<Node>? {
        guard let baseCache = store.state.caches[key] else {
            return nil
        }

        guard let cache = baseCache as? AtomCache<Node> else {
            assertionFailure(
                """
                [Atoms]
                The type of the given atom's value and the cache did not match.
                There might be duplicate keys, make sure that the keys for all atom types are unique.

                Atom: \(Node.self)
                Key: \(type(of: atom.key))
                Detected: \(type(of: baseCache))
                Expected: AtomCache<\(Node.self)>
                """
            )

            // Release the invalid registration as a fallback.
            release(for: key)
            return nil
        }

        return cache
    }

    func lookupOverride<Node: Atom>(of atom: Node) -> Override<Node>? {
        lazy var overrideKey = OverrideKey(atom)
        lazy var typeOverrideKey = OverrideKey(Node.self)

        // OPTIMIZE: Desirable to reduce the number of dictionary lookups which is currently 4 times.
        let baseScopedOverride = scopedOverrides[overrideKey] ?? scopedOverrides[typeOverrideKey]
        let baseOverride = baseScopedOverride ?? overrides[overrideKey] ?? overrides[typeOverrideKey]

        guard let baseOverride else {
            return nil
        }

        guard let override = baseOverride as? Override<Node> else {
            assertionFailure(
                """
                [Atoms]
                Detected an illegal override.
                There might be duplicate keys or logic failure.
                Detected: \(type(of: baseOverride))
                Expected: Override<\(Node.self)>
                """
            )

            return nil
        }

        return override
    }

    func lookupScopeKey<Node: Atom>(of atom: Node, override: Override<Node>?) -> ScopeKey? {
        if override?.isScoped ?? false {
            return scopeKey
        }
        else if let atom = atom as? any Scoped {
            let scopeID = ScopeID(atom.scopeID)
            return inheritedScopeKeys[scopeID]
        }
        else {
            return nil
        }
    }

    func notifyUpdateToObservers() {
        guard !observers.isEmpty || !scopedObservers.isEmpty else {
            return
        }

        let snapshot = snapshot()

        for observer in observers + scopedObservers {
            observer.onUpdate(snapshot)
        }
    }
}

```

## Sources/Atoms/Core/TransactionState.swift

```
@usableFromInline
@MainActor
internal final class TransactionState {
    private var body: (@MainActor () -> @MainActor () -> Void)?
    private var cleanup: (@MainActor () -> Void)?

    let key: AtomKey

    private var termination: (@MainActor () -> Void)?
    private(set) var isTerminated = false

    init(
        key: AtomKey,
        _ body: @MainActor @escaping () -> @MainActor () -> Void
    ) {
        self.key = key
        self.body = body
    }

    var onTermination: (@MainActor () -> Void)? {
        get { termination }
        set {
            guard !isTerminated else {
                newValue?()
                return
            }

            termination = newValue
        }

    }

    func begin() {
        cleanup = body?()
        body = nil
    }

    func commit() {
        cleanup?()
        cleanup = nil
    }

    func terminate() {
        isTerminated = true

        termination?()
        termination = nil
        body = nil
        commit()
    }
}

```

## Sources/Atoms/Core/SubscriberState.swift

```
import Foundation

@MainActor
internal final class SubscriberState {
    let token = SubscriberKey.Token()

    #if !hasFeature(IsolatedDefaultValues)
        nonisolated init() {}
    #endif

    #if compiler(>=6)
        nonisolated(unsafe) var subscribing = Set<AtomKey>()
        nonisolated(unsafe) var unsubscribe: ((Set<AtomKey>) -> Void)?

        // TODO: Use isolated synchronous deinit once it's available.
        // 0371-isolated-synchronous-deinit
        deinit {
            if Thread.isMainThread {
                unsubscribe?(subscribing)
            }
            else {
                Task { @MainActor [unsubscribe, subscribing] in
                    unsubscribe?(subscribing)
                }
            }
        }
    #else
        private var _subscribing = UnsafeUncheckedSendable(Set<AtomKey>())
        private var _unsubscribe = UnsafeUncheckedSendable<((Set<AtomKey>) -> Void)?>(nil)

        var subscribing: Set<AtomKey> {
            _read { yield _subscribing.value }
            _modify { yield &_subscribing.value }
        }

        var unsubscribe: ((Set<AtomKey>) -> Void)? {
            _read { yield _unsubscribe.value }
            _modify { yield &_unsubscribe.value }
        }

        deinit {
            if Thread.isMainThread {
                _unsubscribe.value?(_subscribing.value)
            }
            else {
                Task { @MainActor [_unsubscribe, _subscribing] in
                    _unsubscribe.value?(_subscribing.value)
                }
            }
        }
    #endif
}

```

## Sources/Atoms/Core/Override.swift

```
@usableFromInline
internal protocol OverrideProtocol: Sendable {
    associatedtype Node: Atom

    var isScoped: Bool { get }
    var getValue: @MainActor @Sendable (Node) -> Node.Produced { get }
}

@usableFromInline
internal struct Override<Node: Atom>: OverrideProtocol {
    @usableFromInline
    let isScoped: Bool
    @usableFromInline
    let getValue: @MainActor @Sendable (Node) -> Node.Produced

    @usableFromInline
    init(isScoped: Bool, getValue: @escaping @MainActor @Sendable (Node) -> Node.Produced) {
        self.isScoped = isScoped
        self.getValue = getValue
    }
}

```

## Sources/Atoms/Core/StoreState.swift

```
@MainActor
internal final class StoreState {
    var caches = [AtomKey: any AtomCacheProtocol]()
    var states = [AtomKey: any AtomStateProtocol]()
    var subscriptions = [AtomKey: [SubscriberKey: Subscription]]()

    nonisolated init() {}
}

```

## Sources/Atoms/Core/Graph.swift

```
internal struct Graph: Equatable {
    var dependencies = [AtomKey: Set<AtomKey>]()
    var children = [AtomKey: Set<AtomKey>]()
}

```

## Sources/Atoms/Core/OverrideKey.swift

```
@usableFromInline
internal struct OverrideKey: Hashable, Sendable {
    private let identifier: Identifier

    @usableFromInline
    init<Node: Atom>(_ atom: Node) {
        let key = UnsafeUncheckedSendable<AnyHashable>(atom.key)
        let type = ObjectIdentifier(Node.self)
        identifier = .node(key: key, type: type)
    }

    @usableFromInline
    init<Node: Atom>(_: Node.Type) {
        let type = ObjectIdentifier(Node.self)
        identifier = .type(type)
    }
}

private extension OverrideKey {
    enum Identifier: Hashable, Sendable {
        case node(key: UnsafeUncheckedSendable<AnyHashable>, type: ObjectIdentifier)
        case type(ObjectIdentifier)
    }
}

```

## Sources/Atoms/Core/Subscription.swift

```
@usableFromInline
internal struct Subscription {
    let location: SourceLocation
    let update: @MainActor @Sendable () -> Void
}

```

## Sources/Atoms/Core/ScopeID.swift

```
internal struct ScopeID: Hashable {
    private let id: AnyHashable

    init(_ id: any Hashable) {
        self.id = AnyHashable(id)
    }
}

```

## Sources/Atoms/Core/AtomKey.swift

```
internal struct AtomKey: Hashable, Sendable, CustomStringConvertible {
    private let key: UnsafeUncheckedSendable<AnyHashable>
    private let type: ObjectIdentifier
    private let scopeKey: ScopeKey?
    private let anyAtomType: Any.Type

    var description: String {
        let atomLabel = String(describing: anyAtomType)

        if let scopeKey {
            return atomLabel + "-scoped:\(scopeKey)"
        }
        else {
            return atomLabel
        }
    }

    var isScoped: Bool {
        scopeKey != nil
    }

    init<Node: Atom>(_ atom: Node, scopeKey: ScopeKey?) {
        self.key = UnsafeUncheckedSendable(atom.key)
        self.type = ObjectIdentifier(Node.self)
        self.scopeKey = scopeKey
        self.anyAtomType = Node.self
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(key)
        hasher.combine(type)
        hasher.combine(scopeKey)
    }

    static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.key == rhs.key && lhs.type == rhs.type && lhs.scopeKey == rhs.scopeKey
    }
}

```

## Sources/Atoms/Core/SubscriberKey.swift

```
internal struct SubscriberKey: Hashable {
    @MainActor
    final class Token {}

    private let identifier: ObjectIdentifier

    init(token: Token) {
        identifier = ObjectIdentifier(token)
    }
}

```

## Sources/Atoms/Core/UnsafeUncheckedSendable.swift

```
import os

internal struct UnsafeUncheckedSendable<Value>: @unchecked Sendable {
    var value: Value

    init(_ value: Value) {
        self.value = value
    }
}

extension UnsafeUncheckedSendable: Equatable where Value: Equatable {}
extension UnsafeUncheckedSendable: Hashable where Value: Hashable {}

```

## Sources/Atoms/Core/AtomState.swift

```
@MainActor
internal protocol AtomStateProtocol: AnyObject {
    associatedtype Effect: AtomEffect

    var effect: Effect { get }
    var transactionState: TransactionState? { get set }
}

@MainActor
internal final class AtomState<Effect: AtomEffect>: AtomStateProtocol {
    let effect: Effect
    var transactionState: TransactionState?

    init(effect: Effect) {
        self.effect = effect
    }
}

```

## Sources/Atoms/Core/SourceLocation.swift

```
internal struct SourceLocation: Equatable {
    let fileID: String
    let line: UInt

    init(fileID: String = #fileID, line: UInt = #line) {
        self.fileID = fileID
        self.line = line
    }
}

```

## Sources/Atoms/Core/TopologicalSort.swift

```
internal enum Vertex: Hashable {
    case atom(key: AtomKey)
    case subscriber(key: SubscriberKey)
}

internal struct Edge: Hashable {
    let from: AtomKey
    let to: Vertex
}

internal extension AtomStore {
    /// DFS topological sorting.
    func topologicalSorted(key: AtomKey) -> (
        edges: ReversedCollection<ContiguousArray<Edge>>,
        redundantDependencies: [Vertex: ContiguousArray<AtomKey>]
    ) {
        var trace = Set<Vertex>()
        var edges = ContiguousArray<Edge>()
        var redundantDependencies = [Vertex: ContiguousArray<AtomKey>]()

        func traverse(key: AtomKey, isRedundant: Bool) {
            if let children = graph.children[key] {
                for child in children {
                    traverse(key: child, from: key, isRedundant: isRedundant)
                }
            }

            if let subscriptions = state.subscriptions[key] {
                for subscriberKey in subscriptions.keys {
                    traverse(key: subscriberKey, from: key, isRedundant: isRedundant)
                }
            }
        }

        func traverse(key: AtomKey, from fromKey: AtomKey, isRedundant: Bool) {
            let vertex = Vertex.atom(key: key)
            let isRedundant = isRedundant || trace.contains(vertex)

            trace.insert(vertex)

            // Do not stop traversing downstream even when edges are already traced
            // to analyze the redundant edges later.
            traverse(key: key, isRedundant: isRedundant)

            if isRedundant {
                redundantDependencies[vertex, default: []].append(fromKey)
            }
            else {
                let edge = Edge(from: fromKey, to: vertex)
                edges.append(edge)
            }
        }

        func traverse(key: SubscriberKey, from fromKey: AtomKey, isRedundant: Bool) {
            let vertex = Vertex.subscriber(key: key)
            let isRedundant = isRedundant || trace.contains(vertex)

            trace.insert(vertex)

            if isRedundant {
                redundantDependencies[vertex, default: []].append(fromKey)
            }
            else {
                let edge = Edge(from: fromKey, to: vertex)
                edges.append(edge)
            }
        }

        traverse(key: key, isRedundant: false)

        return (edges: edges.reversed(), redundantDependencies: redundantDependencies)
    }
}

```

## Sources/Atoms/Core/Producer/AtomProducer.swift

```
/// Produces the value of an atom.
public struct AtomProducer<Value> {
    internal typealias Context = AtomProducerContext<Value>

    internal let getValue: @MainActor (Context) -> Value
    internal let manageValue: @MainActor (Value, Context) -> Void
    internal let shouldUpdate: @MainActor (Value, Value) -> Bool
    internal let performUpdate: @MainActor (() -> Void) -> Void

    internal init(
        getValue: @MainActor @escaping (Context) -> Value,
        manageValue: @MainActor @escaping (Value, Context) -> Void = { _, _ in },
        shouldUpdate: @MainActor @escaping (Value, Value) -> Bool = { _, _ in true },
        performUpdate: @MainActor @escaping (() -> Void) -> Void = { update in update() }
    ) {
        self.getValue = getValue
        self.manageValue = manageValue
        self.shouldUpdate = shouldUpdate
        self.performUpdate = performUpdate
    }
}

```

## Sources/Atoms/Core/Producer/AtomProducerContext.swift

```
@MainActor
internal struct AtomProducerContext<Value> {
    private let store: StoreContext
    private let transactionState: TransactionState
    private let update: @MainActor (Value) -> Void

    init(
        store: StoreContext,
        transactionState: TransactionState,
        update: @escaping @MainActor (Value) -> Void
    ) {
        self.store = store
        self.transactionState = transactionState
        self.update = update
    }

    var isTerminated: Bool {
        transactionState.isTerminated
    }

    var onTermination: (@MainActor () -> Void)? {
        get { transactionState.onTermination }
        nonmutating set { transactionState.onTermination = newValue }
    }

    func update(with value: Value) {
        update(value)
    }

    func transaction<T>(_ body: @MainActor (AtomTransactionContext) -> T) -> T {
        transactionState.begin()
        let context = AtomTransactionContext(store: store, transactionState: transactionState)
        defer { transactionState.commit() }
        return body(context)
    }

    #if compiler(>=6)
        func transaction<T, E: Error>(_ body: @MainActor (AtomTransactionContext) async throws(E) -> T) async throws(E) -> T {
            transactionState.begin()
            let context = AtomTransactionContext(store: store, transactionState: transactionState)
            defer { transactionState.commit() }
            return try await body(context)
        }
    #else
        func transaction<T>(_ body: @MainActor (AtomTransactionContext) async throws -> T) async rethrows -> T {
            transactionState.begin()
            let context = AtomTransactionContext(store: store, transactionState: transactionState)
            defer { transactionState.commit() }
            return try await body(context)
        }
    #endif
}

```

## Sources/Atoms/Core/Producer/AtomRefreshProducer.swift

```
/// Produces the refreshed value of an atom.
public struct AtomRefreshProducer<Value> {
    internal typealias Context = AtomProducerContext<Value>

    internal let getValue: @MainActor (Context) async -> Value
    internal let refreshValue: @MainActor (Value, Context) async -> Void

    internal init(
        getValue: @MainActor @escaping (Context) async -> Value,
        refreshValue: @MainActor @escaping (Value, Context) async -> Void = { _, _ in }
    ) {
        self.getValue = getValue
        self.refreshValue = refreshValue
    }
}

```

## Sources/Atoms/Core/Modifier/AsyncAtomModifier.swift

```
/// A modifier that you apply to an atom, producing a new refreshable value modified from the original value.
public protocol AsyncAtomModifier: AtomModifier {
    /// A producer that produces the refreshable value of this atom.
    func refreshProducer(atom: some AsyncAtom<Base>) -> AtomRefreshProducer<Produced>
}

```

## Sources/Atoms/Core/Modifier/AtomModifier.swift

```
public extension Atom {
    /// Applies a modifier to an atom and returns a new atom.
    ///
    /// - Parameter modifier: The modifier to apply to this atom.
    /// - Returns: A new atom that is applied the given modifier.
    func modifier<T: AtomModifier>(_ modifier: T) -> ModifiedAtom<Self, T> {
        ModifiedAtom(atom: self, modifier: modifier)
    }
}

/// A modifier that you apply to an atom, producing a new value modified from the original value.
public protocol AtomModifier: Sendable {
    /// A type representing the stable identity of this modifier.
    associatedtype Key: Hashable & Sendable

    /// A type of base value to be modified.
    associatedtype Base

    /// A type of value the modified atom produces.
    associatedtype Produced

    /// A unique value used to identify the modifier internally.
    var key: Key { get }

    // --- Internal ---

    /// A producer that produces the value of this atom.
    func producer(atom: some Atom<Base>) -> AtomProducer<Produced>
}

```

## Sources/Atoms/Core/Atom/ModifiedAtom.swift

```
/// An atom type that applies a modifier to an atom.
///
/// Use ``Atom/modifier(_:)`` instead of using this atom directly.
public struct ModifiedAtom<Node: Atom, Modifier: AtomModifier>: Atom where Node.Produced == Modifier.Base {
    /// The type of value that this atom produces.
    public typealias Produced = Modifier.Produced

    /// A type representing the stable identity of this atom.
    public struct Key: Hashable, Sendable {
        private let atomKey: Node.Key
        private let modifierKey: Modifier.Key

        fileprivate init(
            atomKey: Node.Key,
            modifierKey: Modifier.Key
        ) {
            self.atomKey = atomKey
            self.modifierKey = modifierKey
        }
    }

    private let atom: Node
    private let modifier: Modifier

    internal init(atom: Node, modifier: Modifier) {
        self.atom = atom
        self.modifier = modifier
    }

    /// A unique value used to identify the atom.
    public var key: Key {
        Key(atomKey: atom.key, modifierKey: modifier.key)
    }

    /// A producer that produces the value of this atom.
    public var producer: AtomProducer<Produced> {
        modifier.producer(atom: atom)
    }
}

extension ModifiedAtom: AsyncAtom where Node: AsyncAtom, Modifier: AsyncAtomModifier {
    /// A producer that produces the refreshable value of this atom.
    public var refreshProducer: AtomRefreshProducer<Produced> {
        modifier.refreshProducer(atom: atom)
    }
}

extension ModifiedAtom: Scoped where Node: Scoped {
    /// A scope ID which is to find a matching scope.
    public var scopeID: Node.ScopeID {
        atom.scopeID
    }
}

```

## Sources/Atoms/Core/Atom/AsyncAtom.swift

```
/// Declares that a type can produce a refreshable value that can be accessed from everywhere.
///
/// Atoms compliant with this protocol are refreshable and can wait until the atom produces
/// its final value.
public protocol AsyncAtom<Produced>: Atom {
    /// A producer that produces the refreshable value of this atom.
    var refreshProducer: AtomRefreshProducer<Produced> { get }
}

```

## Sources/Atoms/Core/Atom/Atom.swift

```
/// Declares that a type can produce a value that can be accessed from everywhere.
///
/// The value produced by an atom is created only when the atom is watched from somewhere,
/// and is immediately released when no longer watched.
public protocol Atom<Produced>: Sendable {
    /// A type representing the stable identity of this atom.
    associatedtype Key: Hashable & Sendable

    /// The type of value that this atom produces.
    associatedtype Produced

    /// The type of effect for managing side effects.
    associatedtype Effect: AtomEffect = EmptyEffect

    /// A type of the context structure to read, watch, and otherwise interact
    /// with other atoms.
    typealias Context = AtomTransactionContext

    /// A type of the context structure to read, set, and otherwise interact
    /// with other atoms.
    typealias CurrentContext = AtomCurrentContext

    /// A unique value used to identify the atom.
    ///
    /// This key don't have to be unique with respect to other atoms in the entire application
    /// because it is identified respecting the metatype of this atom.
    /// If this atom conforms to `Hashable`, it will adopt itself as the `key` by default.
    var key: Key { get }

    /// An effect for managing side effects that are synchronized with this atom's lifecycle.
    ///
    /// - Parameter context: A context structure to read, set, and otherwise
    ///                      interact with other atoms.
    ///
    /// - Returns: An effect for managing side effects.
    @MainActor
    func effect(context: CurrentContext) -> Effect

    // --- Internal ---

    /// A producer that produces the value of this atom.
    var producer: AtomProducer<Produced> { get }
}

public extension Atom {
    @MainActor
    func effect(context: CurrentContext) -> Effect where Effect == EmptyEffect {
        EmptyEffect()
    }
}

public extension Atom where Self == Key {
    var key: Self {
        self
    }
}

```

## Sources/Atoms/Core/Effect/EmptyEffect.swift

```
/// An effect that doesn't produce any effects.
public struct EmptyEffect: AtomEffect {
    /// Creates an empty effect.
    public init() {}
}

```

## Sources/Atoms/Attribute/Refreshable.swift

````
/// An attribute protocol that allows an atom to have a custom refresh behavior.
///
/// It is useful when creating a wrapper atom and you want to transparently refresh the atom underneath.
/// Note that the custom refresh will not be triggered when the atom is overridden.
///
/// ```swift
/// struct UserAtom: ValueAtom, Refreshable, Hashable {
///     func value(context: Context) -> AsyncPhase<User?, Never> {
///         context.watch(FetchUserAtom().phase)
///     }
///
///     func refresh(context: CurrentContext) async -> AsyncPhase<User?, Never> {
///         await context.refresh(FetchUserAtom().phase)
///     }
/// }
///
/// private struct FetchUserAtom: TaskAtom, Hashable {
///     func value(context: Context) async -> User? {
///         await fetchUser()
///     }
/// }
/// ```
///
public protocol Refreshable where Self: Atom {
    /// Refreshes and then return a result value.
    ///
    /// The value returned by this method will be cached as a new value when
    /// this atom is refreshed.
    ///
    /// - Parameter context: A context structure to read, set, and otherwise interact
    ///                      with other atoms.
    ///
    /// - Returns: A refreshed value.
    @MainActor
    func refresh(context: CurrentContext) async -> Produced
}

````

## Sources/Atoms/Attribute/Resettable.swift

````
/// An attribute protocol that allows an atom to have a custom reset behavior.
///
/// It is useful when creating a wrapper atom and you want to transparently reset the atom underneath.
/// Note that the custom reset will not be triggered when the atom is overridden.
///
/// ```swift
/// struct UserAtom: ValueAtom, Resettable, Hashable {
///     func value(context: Context) -> AsyncPhase<User?, Never> {
///         context.watch(FetchUserAtom().phase)
///     }
///
///     func reset(context: CurrentContext) {
///         context.reset(FetchUserAtom())
///     }
/// }
///
/// private struct FetchUserAtom: TaskAtom, Hashable {
///     func value(context: Context) async -> User? {
///         await fetchUser()
///     }
/// }
/// ```
///
public protocol Resettable where Self: Atom {
    /// Arbitrary reset method to be executed on atom reset.
    ///
    /// This is arbitrary custom reset method that replaces regular atom reset functionality.
    ///
    /// - Parameter context: A context structure to read, set, and otherwise interact
    ///                      with other atoms.
    @MainActor
    func reset(context: CurrentContext)
}

````

## Sources/Atoms/Attribute/KeepAlive.swift

````
/// An attribute protocol to allow the value of an atom to continue being retained
/// even after they are no longer watched.
///
/// Note that overridden or scoped atoms are not retained even with this attribute.
///
/// ## Example
///
/// ```swift
/// struct SharedPollingServiceAtom: ValueAtom, KeepAlive, Hashable {
///     func value(context: Context) -> PollingService {
///         PollingService()
///     }
/// }
/// ```
///
public protocol KeepAlive where Self: Atom {}

````

## Sources/Atoms/Attribute/Scoped.swift

````
/// An attribute protocol to preserve the atom state in the scope nearest to the ancestor
/// of where it is used and prevents it from being shared out of scope.
///
/// If multiple scopes are nested, you can define an arbitrary `scopeID` to ensure that
/// values are stored in a particular scope.
/// The atom with `scopeID` searches for the nearest ``AtomScope`` with the matching ID in
/// ancestor views, and if not found, the state is shared within the app.
///
/// Note that other atoms that depend on the scoped atom will be in a shared state and must be
/// given this attribute as well in order to scope them as well.
///
/// ## Example
///
/// ```swift
/// struct SearchScopeID: Hashable {}
///
/// struct SearchQueryAtom: StateAtom, Scoped, Hashable {
///     var scopeID: SearchScopeID {
///         SearchScopeID()
///     }
///
///     func defaultValue(context: Context) -> String {
///          ""
///     }
/// }
///
/// AtomScope(id: SearchScopeID()) {
///     SearchPane()
/// }
/// ```
///
public protocol Scoped where Self: Atom {
    /// A type of the scope ID which is to find a matching scope.
    associatedtype ScopeID: Hashable = DefaultScopeID

    /// A scope ID which is to find a matching scope.
    var scopeID: ScopeID { get }
}

public extension Scoped where ScopeID == DefaultScopeID {
    /// A scope ID which is to find a matching scope.
    var scopeID: ScopeID {
        DefaultScopeID()
    }
}

/// A default scope ID to find a matching scope inbetween scoped atoms and ``AtomScope``.
public struct DefaultScopeID: Hashable {
    /// Creates a new default scope ID which is always indentical.
    public init() {}
}

````

## Sources/Atoms/Modifier/AnimationModifier.swift

````
import SwiftUI

public extension Atom {
    /// Animates the view watching the atom when the value updates.
    ///
    /// Note that this modifier does nothing when being watched by other atoms.
    ///
    /// ```swift
    /// struct TextAtom: ValueAtom, Hashable {
    ///     func value(context: Context) -> String {
    ///         ""
    ///     }
    /// }
    ///
    /// struct ExampleView: View {
    ///     @Watch(TextAtom().animation())
    ///     var text
    ///
    ///     var body: some View {
    ///         Text(text)
    ///     }
    /// }
    /// ```
    ///
    /// - Parameter animation: The animation to apply to the value.
    ///
    /// - Returns: An atom that animates the view watching the atom when the value updates.
    func animation(_ animation: Animation? = .default) -> ModifiedAtom<Self, AnimationModifier<Produced>> {
        modifier(AnimationModifier(animation: animation))
    }
}

/// A modifier that animates the view watching the atom when the value updates.
///
/// Use ``Atom/animation(_:)`` instead of using this modifier directly.
public struct AnimationModifier<Produced>: AtomModifier {
    /// A type of base value to be modified.
    public typealias Base = Produced

    /// A type of value the modified atom produces.
    public typealias Produced = Produced

    /// A type representing the stable identity of this atom associated with an instance.
    public struct Key: Hashable, Sendable {
        private let animation: Animation?

        fileprivate init(animation: Animation?) {
            self.animation = animation
        }
    }

    private let animation: Animation?

    internal init(animation: Animation?) {
        self.animation = animation
    }

    /// A unique value used to identify the modifier internally.
    public var key: Key {
        Key(animation: animation)
    }

    /// A producer that produces the value of this atom.
    public func producer(atom: some Atom<Base>) -> AtomProducer<Produced> {
        AtomProducer { context in
            context.transaction { $0.watch(atom) }
        } performUpdate: { update in
            withAnimation(animation, update)
        }
    }
}

````

## Sources/Atoms/Modifier/ChangesOfModifier.swift

````
public extension Atom {
    /// Derives a partial property with the specified key path from the original atom and prevent it
    /// from updating its downstream when its new value is equivalent to old value.
    ///
    /// ```swift
    /// struct IntAtom: ValueAtom, Hashable {
    ///     func value(context: Context) -> Int {
    ///         12345
    ///     }
    /// }
    ///
    /// struct ExampleView: View {
    ///     @Watch(IntAtom().changes(of: \.description))
    ///     var description
    ///
    ///     var body: some View {
    ///         Text(description)
    ///     }
    /// }
    /// ```
    ///
    /// - Parameter keyPath: A key path for the property of the original atom value.
    ///
    /// - Returns: An atom that provides the partial property of the original atom value.
    #if compiler(>=6) || hasFeature(InferSendableFromCaptures)
        func changes<T: Equatable>(
            of keyPath: any KeyPath<Produced, T> & Sendable
        ) -> ModifiedAtom<Self, ChangesOfModifier<Produced, T>> {
            modifier(ChangesOfModifier(keyPath: keyPath))
        }
    #else
        func changes<T: Equatable>(
            of keyPath: KeyPath<Produced, T>
        ) -> ModifiedAtom<Self, ChangesOfModifier<Produced, T>> {
            modifier(ChangesOfModifier(keyPath: keyPath))
        }
    #endif
}

/// A modifier that derives a partial property with the specified key path from the original atom
/// and prevent it from updating its downstream when its new value is equivalent to old value.
///
/// Use ``Atom/changes(of:)`` instead of using this modifier directly.
public struct ChangesOfModifier<Base, Produced: Equatable>: AtomModifier {
    /// A type of base value to be modified.
    public typealias Base = Base

    /// A type of value the modified atom produces.
    public typealias Produced = Produced

    #if compiler(>=6) || hasFeature(InferSendableFromCaptures)
        /// A type representing the stable identity of this modifier.
        public struct Key: Hashable, Sendable {
            private let keyPath: any KeyPath<Base, Produced> & Sendable

            fileprivate init(keyPath: any KeyPath<Base, Produced> & Sendable) {
                self.keyPath = keyPath
            }
        }

        private let keyPath: any KeyPath<Base, Produced> & Sendable

        internal init(keyPath: any KeyPath<Base, Produced> & Sendable) {
            self.keyPath = keyPath
        }

        /// A unique value used to identify the modifier internally.
        public var key: Key {
            Key(keyPath: keyPath)
        }
    #else
        public struct Key: Hashable, Sendable {
            private let keyPath: UnsafeUncheckedSendable<KeyPath<Base, Produced>>

            fileprivate init(keyPath: UnsafeUncheckedSendable<KeyPath<Base, Produced>>) {
                self.keyPath = keyPath
            }
        }

        private let _keyPath: UnsafeUncheckedSendable<KeyPath<Base, Produced>>
        private var keyPath: KeyPath<Base, Produced> {
            _keyPath.value
        }

        internal init(keyPath: KeyPath<Base, Produced>) {
            _keyPath = UnsafeUncheckedSendable(keyPath)
        }

        /// A unique value used to identify the modifier internally.
        public var key: Key {
            Key(keyPath: _keyPath)
        }
    #endif

    /// A producer that produces the value of this atom.
    public func producer(atom: some Atom<Base>) -> AtomProducer<Produced> {
        AtomProducer { context in
            let value = context.transaction { $0.watch(atom) }
            return value[keyPath: keyPath]
        } shouldUpdate: { oldValue, newValue in
            oldValue != newValue
        }
    }
}

````

## Sources/Atoms/Modifier/ChangesModifier.swift

````
public extension Atom where Produced: Equatable {
    /// Prevents the atom from updating its downstream when its new value is equivalent to old value.
    ///
    /// ```swift
    /// struct FlagAtom: StateAtom, Hashable {
    ///     func defaultValue(context: Context) -> Bool {
    ///         true
    ///     }
    /// }
    ///
    /// struct ExampleView: View {
    ///     @Watch(FlagAtom().changes)
    ///     var flag
    ///
    ///     var body: some View {
    ///         if flag {
    ///             Text("true")
    ///         }
    ///         else {
    ///             Text("false")
    ///         }
    ///     }
    /// }
    /// ```
    ///
    var changes: ModifiedAtom<Self, ChangesModifier<Produced>> {
        modifier(ChangesModifier())
    }
}

/// A modifier that prevents the atom from updating its child views or atoms when
/// its new value is the same as its old value.
///
/// Use ``Atom/changes`` instead of using this modifier directly.
public struct ChangesModifier<Produced: Equatable>: AtomModifier {
    /// A type of base value to be modified.
    public typealias Base = Produced

    /// A type of value the modified atom produces.
    public typealias Produced = Produced

    /// A type representing the stable identity of this atom associated with an instance.
    public struct Key: Hashable, Sendable {}

    /// A unique value used to identify the modifier internally.
    public var key: Key {
        Key()
    }

    /// A producer that produces the value of this atom.
    public func producer(atom: some Atom<Base>) -> AtomProducer<Produced> {
        AtomProducer { context in
            context.transaction { $0.watch(atom) }
        } shouldUpdate: { oldValue, newValue in
            oldValue != newValue
        }
    }
}

````

## Sources/Atoms/Modifier/TaskPhaseModifier.swift

````
public extension TaskAtom {
    /// Converts the `Task` that the original atom provides into ``AsyncPhase`` that
    /// changes overtime.
    ///
    /// ```swift
    /// struct AsyncIntAtom: TaskAtom, Hashable {
    ///     func value(context: Context) async -> Int {
    ///         try? await Task.sleep(nanoseconds: 1_000_000_000)
    ///         return 12345
    ///     }
    /// }
    ///
    /// struct ExampleView: View {
    ///     @Watch(AsyncIntAtom().phase)
    ///     var intPhase
    ///
    ///     var body: some View {
    ///         switch intPhase {
    ///         case .success(let value):
    ///             Text("Value is \(value)")
    ///
    ///         case .suspending:
    ///             Text("Loading")
    ///         }
    ///     }
    /// }
    /// ```
    ///
    var phase: ModifiedAtom<Self, TaskPhaseModifier<Success, Never>> {
        modifier(TaskPhaseModifier())
    }
}

public extension ThrowingTaskAtom {
    /// Converts the `Task` that the original atom provides into ``AsyncPhase`` that
    /// changes overtime.
    ///
    /// ```swift
    /// struct AsyncIntAtom: ThrowingTaskAtom, Hashable {
    ///     func value(context: Context) async throws -> Int {
    ///         try await Task.sleep(nanoseconds: 1_000_000_000)
    ///         return 12345
    ///     }
    /// }
    ///
    /// struct ExampleView: View {
    ///     @Watch(AsyncIntAtom().phase)
    ///     var intPhase
    ///
    ///     var body: some View {
    ///         switch intPhase {
    ///         case .success(let value):
    ///             Text("Value is \(value)")
    ///
    ///         case .failure(let error):
    ///             Text("Error is \(error)")
    ///
    ///         case .suspending:
    ///             Text("Loading")
    ///         }
    ///     }
    /// }
    /// ```
    ///
    var phase: ModifiedAtom<Self, TaskPhaseModifier<Success, any Error>> {
        modifier(TaskPhaseModifier())
    }
}

/// An atom that provides a sequential value of the base atom as an enum
/// representation ``AsyncPhase`` that changes overtime.
///
/// Use ``TaskAtom/phase`` or ``ThrowingTaskAtom/phase`` instead of using this modifier directly.
public struct TaskPhaseModifier<Success: Sendable, Failure: Error>: AsyncAtomModifier {
    /// A type of base value to be modified.
    public typealias Base = Task<Success, Failure>

    /// A type of value the modified atom produces.
    public typealias Produced = AsyncPhase<Success, Failure>

    /// A type representing the stable identity of this atom associated with an instance.
    public struct Key: Hashable, Sendable {}

    /// A unique value used to identify the modifier internally.
    public var key: Key {
        Key()
    }

    /// A producer that produces the value of this atom.
    public func producer(atom: some Atom<Base>) -> AtomProducer<Produced> {
        AtomProducer { context in
            let baseTask = context.transaction { $0.watch(atom) }
            let task = Task {
                let phase = await AsyncPhase(baseTask.result)

                if !Task.isCancelled {
                    context.update(with: phase)
                }
            }

            context.onTermination = task.cancel
            return .suspending
        }
    }

    /// A producer that produces the refreshable value of this atom.
    public func refreshProducer(atom: some AsyncAtom<Base>) -> AtomRefreshProducer<Produced> {
        AtomRefreshProducer { context in
            let task = await context.transaction { context in
                await context.refresh(atom)
                return context.watch(atom)
            }

            return await AsyncPhase(task.result)
        }
    }
}

````

## Sources/Atoms/Atom/TaskAtom.swift

````
/// An atom type that provides a nonthrowing `Task` from the given asynchronous function.
///
/// This atom guarantees that the task to be identical instance and its state can be shared
/// at anywhere even when they are accessed simultaneously from multiple locations.
///
/// - SeeAlso: ``ThrowingTaskAtom``
/// - SeeAlso: ``Suspense``
///
/// ## Output Value
///
/// Task<Self.Value, Never>
///
/// ## Example
///
/// ```swift
/// struct AsyncTextAtom: TaskAtom, Hashable {
///     func value(context: Context) async -> String {
///         try? await Task.sleep(nanoseconds: 1_000_000_000)
///         return "Swift"
///     }
/// }
///
/// struct DelayedTitleView: View {
///     @Watch(AsyncTextAtom())
///     var text
///
///     var body: some View {
///         Suspense(text) { text in
///             Text(text)
///         } suspending: {
///             Text("Loading...")
///         }
///     }
/// }
/// ```
///
public protocol TaskAtom: AsyncAtom where Produced == Task<Success, Never> {
    /// The type of success value that this atom produces.
    associatedtype Success: Sendable

    /// Asynchronously produces a value to be provided via this atom.
    ///
    /// This asynchronous method is converted to a `Task` internally, and if it will be
    /// cancelled by downstream atoms or views, this method will also be cancelled.
    ///
    /// - Parameter context: A context structure to read, watch, and otherwise
    ///                      interact with other atoms.
    ///
    /// - Returns: The process's result.
    @MainActor
    func value(context: Context) async -> Success
}

public extension TaskAtom {
    var producer: AtomProducer<Produced> {
        AtomProducer { context in
            Task {
                await context.transaction(value)
            }
        } manageValue: { task, context in
            context.onTermination = task.cancel
        }
    }

    var refreshProducer: AtomRefreshProducer<Produced> {
        AtomRefreshProducer { context in
            Task {
                await context.transaction(value)
            }
        } refreshValue: { task, context in
            context.onTermination = task.cancel

            await withTaskCancellationHandler {
                _ = await task.result
            } onCancel: {
                task.cancel()
            }
        }
    }
}

````

## Sources/Atoms/Atom/ValueAtom.swift

````
/// An atom type that provides a read-only value.
///
/// The value is cached until it will no longer be watched or any of watching atoms will notify update.
/// This atom can be used to combine one or more other atoms and transform result to another value.
/// Moreover, it can also be used to do dependency injection in compile safe and overridable for testing,
/// by providing a dependency instance required in another atom.
///
/// ## Output Value
///
/// Self.Value
///
/// ## Example
///
/// ```swift
/// struct CharacterCountAtom: ValueAtom, Hashable {
///     func value(context: Context) -> Int {
///         let text = context.watch(TextAtom())
///         return text.count
///     }
/// }
///
/// struct CharacterCountView: View {
///     @Watch(CharacterCountAtom())
///     var count
///
///     var body: some View {
///         Text("Character count: \(count)")
///     }
/// }
/// ```
///
public protocol ValueAtom: Atom {
    /// The type of value that this atom produces.
    associatedtype Value

    /// Creates a constant value to be provided via this atom.
    ///
    /// This method is called only when this atom is actually used, and is cached until it will
    /// no longer be watched or any of watching atoms will be updated.
    ///
    /// - Parameter context: A context structure to read, watch, and otherwise
    ///                      interact with other atoms.
    ///
    /// - Returns: A constant value.
    @MainActor
    func value(context: Context) -> Value
}

public extension ValueAtom {
    var producer: AtomProducer<Value> {
        AtomProducer { context in
            context.transaction(value)
        }
    }
}

````

## Sources/Atoms/Atom/AsyncPhaseAtom.swift

````
/// An atom that provides an ``AsyncPhase`` value from the asynchronous throwable function.
///
/// The value produced by the given asynchronous throwable function will be converted into
/// an enum representation ``AsyncPhase`` that changes when the process is done or thrown an error.
///
/// ## Output Value
///
/// ``AsyncPhase``<Self.Success, Self.Failure>
///
/// ## Example
///
/// ```swift
/// struct AsyncTextAtom: AsyncPhaseAtom, Hashable {
///     func value(context: Context) async throws -> String {
///         try await Task.sleep(nanoseconds: 1_000_000_000)
///         return "Swift"
///     }
/// }
///
/// struct DelayedTitleView: View {
///     @Watch(AsyncTextAtom())
///     var text
///
///     var body: some View {
///         switch text {
///         case .success(let text):
///             Text(text)
///
///         case .suspending:
///             Text("Loading")
///
///         case .failure:
///             Text("Failed")
///     }
/// }
/// ```
///
public protocol AsyncPhaseAtom: AsyncAtom where Produced == AsyncPhase<Success, Failure> {
    /// The type of success value that this atom produces.
    associatedtype Success

    #if compiler(>=6)
        /// The type of errors that this atom produces.
        associatedtype Failure: Error

        /// Asynchronously produces a value to be provided via this atom.
        ///
        /// Values provided or errors thrown by this method are converted to the unified enum
        /// representation ``AsyncPhase``.
        ///
        /// - Parameter context: A context structure to read, watch, and otherwise
        ///                      interact with other atoms.
        ///
        /// - Throws: The error that occurred during the process of creating the resulting value.
        ///
        /// - Returns: The process's result.
        @MainActor
        func value(context: Context) async throws(Failure) -> Success
    #else
        /// The type of errors that this atom produces.
        typealias Failure = any Error

        /// Asynchronously produces a value to be provided via this atom.
        ///
        /// Values provided or errors thrown by this method are converted to the unified enum
        /// representation ``AsyncPhase``.
        ///
        /// - Parameter context: A context structure to read, watch, and otherwise
        ///                      interact with other atoms.
        ///
        /// - Throws: The error that occurred during the process of creating the resulting value.
        ///
        /// - Returns: The process's result.
        @MainActor
        func value(context: Context) async throws -> Success
    #endif
}

public extension AsyncPhaseAtom {
    var producer: AtomProducer<Produced> {
        AtomProducer { context in
            let task = Task {
                #if compiler(>=6)
                    do throws(Failure) {
                        let value = try await context.transaction(value)

                        if !Task.isCancelled {
                            context.update(with: .success(value))
                        }
                    }
                    catch {
                        if !Task.isCancelled {
                            context.update(with: .failure(error))
                        }
                    }
                #else
                    do {
                        let value = try await context.transaction(value)

                        if !Task.isCancelled {
                            context.update(with: .success(value))
                        }
                    }
                    catch {
                        if !Task.isCancelled {
                            context.update(with: .failure(error))
                        }
                    }
                #endif
            }

            context.onTermination = task.cancel
            return .suspending
        }
    }

    var refreshProducer: AtomRefreshProducer<Produced> {
        AtomRefreshProducer { context in
            var phase = Produced.suspending

            let task = Task {
                #if compiler(>=6)
                    do throws(Failure) {
                        let value = try await context.transaction(value)

                        if !Task.isCancelled {
                            phase = .success(value)
                        }
                    }
                    catch {
                        if !Task.isCancelled {
                            phase = .failure(error)
                        }
                    }
                #else
                    do {
                        let value = try await context.transaction(value)

                        if !Task.isCancelled {
                            phase = .success(value)
                        }
                    }
                    catch {
                        if !Task.isCancelled {
                            phase = .failure(error)
                        }
                    }
                #endif
            }

            context.onTermination = task.cancel

            return await withTaskCancellationHandler {
                await task.value
                return phase
            } onCancel: {
                task.cancel()
            }
        }
    }
}

````

## Sources/Atoms/Atom/ThrowingTaskAtom.swift

````
/// An atom type that provides a throwing `Task` from the given asynchronous, throwing function.
///
/// This atom guarantees that the task to be identical instance and its state can be shared
/// at anywhere even when they are accessed simultaneously from multiple locations.
///
/// - SeeAlso: ``TaskAtom``
/// - SeeAlso: ``Suspense``
///
/// ## Output Value
///
/// Task<Self.Value, any Error>
///
/// ## Example
///
/// ```swift
/// struct AsyncTextAtom: ThrowingTaskAtom, Hashable {
///     func value(context: Context) async throws -> String {
///         try await Task.sleep(nanoseconds: 1_000_000_000)
///         return "Swift"
///     }
/// }
///
/// struct DelayedTitleView: View {
///     @Watch(AsyncTextAtom())
///     var text
///
///     var body: some View {
///         Suspense(text) { text in
///             Text(text)
///         } suspending: {
///             Text("Loading")
///         } catch: {
///             Text("Failed")
///         }
///     }
/// }
/// ```
///
public protocol ThrowingTaskAtom: AsyncAtom where Produced == Task<Success, any Error> {
    /// The type of success value that this atom produces.
    associatedtype Success: Sendable

    /// Asynchronously produces a value to be provided via this atom.
    ///
    /// This asynchronous method is converted to a `Task` internally, and if it will be
    /// cancelled by downstream atoms or views, this method will also be cancelled.
    ///
    /// - Parameter context: A context structure to read, watch, and otherwise
    ///                      interact with other atoms.
    ///
    /// - Throws: The error that occurred during the process of creating the resulting value.
    ///
    /// - Returns: The process's result.
    @MainActor
    func value(context: Context) async throws -> Success
}

public extension ThrowingTaskAtom {
    var producer: AtomProducer<Produced> {
        AtomProducer { context in
            Task {
                try await context.transaction(value)
            }
        } manageValue: { task, context in
            context.onTermination = task.cancel
        }
    }

    var refreshProducer: AtomRefreshProducer<Produced> {
        AtomRefreshProducer { context in
            Task {
                try await context.transaction(value)
            }
        } refreshValue: { task, context in
            context.onTermination = task.cancel

            await withTaskCancellationHandler {
                _ = await task.result
            } onCancel: {
                task.cancel()
            }
        }
    }
}

````

## Sources/Atoms/Atom/AsyncSequenceAtom.swift

````
/// An atom type that provides asynchronous, sequential elements of the given `AsyncSequence`
/// as an ``AsyncPhase`` value.
///
/// The sequential elements emitted by the `AsyncSequence` will be converted into an enum representation
/// ``AsyncPhase`` that changes overtime. When the sequence emits new elements, it notifies changes to
/// downstream atoms and views, so that they can consume it without suspension points which spawn with
/// `await` keyword.
///
/// ## Output Value
///
/// ``AsyncPhase``<Self.Sequence.Element, any Error>
///
/// ## Example
///
/// ```swift
/// struct QuakeMonitorAtom: AsyncSequenceAtom, Hashable {
///     func sequence(context: Context) -> AsyncStream<Quake> {
///         AsyncStream { continuation in
///             let monitor = QuakeMonitor()
///             monitor.quakeHandler = { quake in
///                 continuation.yield(quake)
///             }
///             continuation.onTermination = { @Sendable _ in
///                 monitor.stopMonitoring()
///             }
///             monitor.startMonitoring()
///         }
///     }
/// }
///
/// struct QuakeMonitorView: View {
///     @Watch(QuakeMonitorAtom())
///     var quakes
///
///     var body: some View {
///         switch quakes {
///         case .suspending, .failure:
///             Text("Calm")
///
///         case .success(let quake):
///             Text("Quake: \(quake.date)")
///         }
///     }
/// }
/// ```
///
public protocol AsyncSequenceAtom: AsyncAtom where Produced == AsyncPhase<Sequence.Element, any Error> {
    /// The type of asynchronous sequence that this atom manages.
    associatedtype Sequence: AsyncSequence where Sequence.Element: Sendable

    /// Creates an asynchronous sequence to be started when this atom is actually used.
    ///
    /// The sequence that is produced by this method must be instantiated anew each time this method
    /// is called. Otherwise, it could throw a fatal error because Swift Concurrency  doesn't allow
    /// single `AsyncSequence` instance to be shared between multiple locations.
    ///
    /// - Parameter context: A context structure to read, watch, and otherwise
    ///                      interact with other atoms.
    ///
    /// - Returns: An asynchronous sequence that produces asynchronous, sequential elements.
    @MainActor
    func sequence(context: Context) -> Sequence
}

public extension AsyncSequenceAtom {
    var producer: AtomProducer<Produced> {
        AtomProducer { context in
            let sequence = context.transaction(sequence)
            let task = Task {
                do {
                    for try await element in sequence {
                        if !Task.isCancelled {
                            context.update(with: .success(element))
                        }
                    }
                }
                catch {
                    if !Task.isCancelled {
                        context.update(with: .failure(error))
                    }
                }
            }

            context.onTermination = task.cancel
            return .suspending
        }
    }

    var refreshProducer: AtomRefreshProducer<Produced> {
        AtomRefreshProducer { context in
            let sequence = context.transaction(sequence)
            let task = Task {
                var phase = Produced.suspending

                do {
                    for try await element in sequence {
                        if !Task.isCancelled {
                            phase = .success(element)
                        }
                    }
                }
                catch {
                    if !Task.isCancelled {
                        phase = .failure(error)
                    }
                }

                return phase
            }

            context.onTermination = task.cancel

            return await withTaskCancellationHandler {
                await task.value
            } onCancel: {
                task.cancel()
            }
        }
    }
}

````

## Sources/Atoms/Atom/StateAtom.swift

````
/// An atom type that provides a read-write state value.
///
/// This atom provides a mutable state value that can be accessed from anywhere, and it notifies changes
/// to downstream atoms and views.
///
/// ## Output Value
///
/// Self.Value
///
/// ## Example
///
/// ```swift
/// struct CounterAtom: StateAtom, Hashable {
///     func defaultValue(context: Context) -> Int {
///         0
///     }
/// }
///
/// struct CounterView: View {
///     @WatchState(CounterAtom())
///     var count
///
///     var body: some View {
///         Stepper("Count: \(count)", value: $count)
///     }
/// }
/// ```
///
public protocol StateAtom: Atom {
    /// The type of value that this atom produces.
    associatedtype Value

    /// Creates a default value of the state to be provided via this atom.
    ///
    /// The value returned from this method will be the default state value. When this atom is reset,
    /// the state will revert to this value.
    ///
    /// - Parameter context: A context structure to read, watch, and otherwise
    ///                      interact with other atoms.
    ///
    /// - Returns: A default value of state.
    @MainActor
    func defaultValue(context: Context) -> Value
}

public extension StateAtom {
    var producer: AtomProducer<Value> {
        AtomProducer { context in
            context.transaction(defaultValue)
        }
    }
}

````

## Sources/Atoms/Atom/ObservableObjectAtom.swift

````
import Foundation

/// An atom type that instantiates an observable object.
///
/// When published properties of the observable object provided through this atom changes, it
/// notifies updates to downstream atoms and views that are watching this atom.
/// In case you want to get another atom value from the context later by methods in that
/// observable object, you can pass it as ``AtomContext``.
///
/// - Note: If you watch other atoms through the context passed as parameter, the observable
///         object itself will be re-created with fresh state when the watching atom is updated.
///
/// ## Output Value
///
/// Self.ObjectType
///
/// ## Example
///
/// ```swift
/// class Contact: ObservableObject {
///     @Published var name = ""
///     @Published var age = 20
///
///     func haveBirthday() {
///         age += 1
///     }
/// }
///
/// struct ContactAtom: ObservableObjectAtom, Hashable {
///     func object(context: Context) -> Contact {
///         Contact()
///     }
/// }
///
/// struct ContactView: View {
///     @WatchStateObject(ContactAtom())
///     var contact
///
///     var body: some View {
///         VStack {
///             TextField("Enter your name", text: $contact.name)
///             Text("Age: \(contact.age)")
///             Button("Celebrate your birthday!") {
///                 contact.haveBirthday()
///             }
///         }
///     }
/// }
/// ```
///
public protocol ObservableObjectAtom: Atom where Produced == ObjectType {
    /// The type of observable object that this atom produces.
    associatedtype ObjectType: ObservableObject

    /// Creates an observed object when this atom is actually used.
    ///
    /// The observable object that returned from this method is managed internally and notifies
    /// its updates to downstream atoms and views are watching this atom.
    ///
    /// - Parameter context: A context structure to read, watch, and otherwise
    ///                      interact with other atoms.
    ///
    /// - Returns: An observable object that notifies its updates over time.
    @MainActor
    func object(context: Context) -> ObjectType
}

public extension ObservableObjectAtom {
    var producer: AtomProducer<Produced> {
        AtomProducer { context in
            context.transaction(object)
        } manageValue: { object, context in
            var task: Task<Void, Never>?
            let cancellable = object
                .objectWillChange
                .sink { [weak object] _ in
                    // Wait until the object's property is set, because `objectWillChange`
                    // emits an event before the property is updated.
                    task?.cancel()
                    task = Task { @MainActor in
                        if let object, !Task.isCancelled, !context.isTerminated {
                            context.update(with: object)
                        }
                    }
                }

            context.onTermination = {
                task?.cancel()
                cancellable.cancel()
            }
        }
    }
}

````

## Sources/Atoms/Atom/PublisherAtom.swift

````
@preconcurrency import Combine

/// An atom type that provides a sequence of values of the given `Publisher` as an ``AsyncPhase`` value.
///
/// The sequential values emitted by the `Publisher` will be converted into an enum representation
/// ``AsyncPhase`` that changes overtime. When the publisher emits new results, it notifies changes to
/// downstream atoms and views, so that they can consume it without managing subscription.
///
/// ## Output Value
///
/// AsyncPhase<Self.Publisher.Output, Self.Publisher.Failure>
///
/// ## Example
///
/// ```swift
/// struct TimerAtom: PublisherAtom, Hashable {
///     func publisher(context: Context) -> AnyPublisher<Date, Never> {
///         Timer.publish(every: 1, on: .main, in: .default)
///             .autoconnect()
///             .eraseToAnyPublisher()
///     }
/// }
///
/// struct TimerView: View {
///     @Watch(TimerAtom())
///     var timer
///
///     var body: some View {
///         switch timer {
///         case .suspending:
///             Text("Waiting")
///
///         case .success(let date):
///             Text("Now: \(date)")
///         }
///     }
/// }
/// ```
///
public protocol PublisherAtom: AsyncAtom where Produced == AsyncPhase<Publisher.Output, Publisher.Failure> {
    /// The type of publisher that this atom manages.
    associatedtype Publisher: Combine.Publisher where Publisher.Output: Sendable

    /// Creates a publisher to be subscribed when this atom is actually used.
    ///
    /// The publisher that is produced by this method must be instantiated anew each time this method
    /// is called. Otherwise, a cold publisher which has internal state can get result to produce
    /// non-reproducible results when it is newly subscribed.
    ///
    /// - Parameter context: A context structure to read, watch, and otherwise
    ///                      interact with other atoms.
    ///
    /// - Returns: A publisher that produces a sequence of values over time.
    @MainActor
    func publisher(context: Context) -> Publisher
}

public extension PublisherAtom {
    var producer: AtomProducer<Produced> {
        AtomProducer { context in
            let results = context.transaction(publisher).results
            let task = Task {
                for await result in results {
                    if !Task.isCancelled {
                        context.update(with: AsyncPhase(result))
                    }
                }
            }

            context.onTermination = task.cancel
            return .suspending
        }
    }

    var refreshProducer: AtomRefreshProducer<Produced> {
        AtomRefreshProducer { context in
            let results = context.transaction(publisher).results
            let task = Task {
                var phase = Produced.suspending

                for await result in results {
                    if !Task.isCancelled {
                        phase = AsyncPhase(result)
                    }
                }

                return phase
            }

            context.onTermination = task.cancel

            return await withTaskCancellationHandler {
                await task.value
            } onCancel: {
                task.cancel()
            }
        }
    }
}

private extension Publisher where Output: Sendable {
    var results: AsyncStream<Result<Output, Failure>> {
        AsyncStream { continuation in
            let cancellable = map(Result.success)
                .catch { Just(.failure($0)) }
                .sink(
                    receiveCompletion: { _ in
                        continuation.finish()
                    },
                    receiveValue: { result in
                        continuation.yield(result)
                    }
                )

            continuation.onTermination = { termination in
                if case .cancelled = termination {
                    cancellable.cancel()
                }
            }
        }
    }
}

````

## Sources/Atoms/Effect/ReleaseEffect.swift

```
/// An atom effect that performs an arbitrary action when the atom is no longer watched and released.
public struct ReleaseEffect: AtomEffect {
    private let action: @MainActor () -> Void

    /// Creates an atom effect that performs the given action when the atom is released.
    public init(perform action: @MainActor @escaping () -> Void) {
        self.action = action
    }

    /// A lifecycle event that is triggered when the atom is no longer watched and released.
    public func released(context: Context) {
        action()
    }
}

```

## Sources/Atoms/Effect/InitializeEffect.swift

```
/// An atom effect that performs an arbitrary action when the atom is first used and initialized,
/// or once it is released and re-initialized again.
public struct InitializeEffect: AtomEffect {
    private let action: @MainActor () -> Void

    /// Creates an atom effect that performs the given action when the atom is initialized.
    public init(perform action: @MainActor @escaping () -> Void) {
        self.action = action
    }

    /// A lifecycle event that is triggered when the atom is first used and initialized,
    /// or once it is released and re-initialized again.
    public func initialized(context: Context) {
        action()
    }
}

```

## Sources/Atoms/Effect/AtomEffect.swift

```
/// Declares side effects that are synchronized with the atom's lifecycle.
///
/// If this effect is attached to atoms via ``Atom/effect(context:)``, the effect is
/// initialized the first time the atom is used, and the instance will be retained
/// until the atom is released, thus it allows to declare stateful side effects.
///
/// SeeAlso: ``InitializeEffect``
/// SeeAlso: ``UpdateEffect``
/// SeeAlso: ``ReleaseEffect``
/// SeeAlso: ``MergedEffect``
@MainActor
public protocol AtomEffect {
    /// A type of the context structure to read, set, and otherwise interact
    /// with other atoms.
    typealias Context = AtomCurrentContext

    /// A lifecycle event that is triggered when the atom is first used and initialized,
    /// or once it is released and re-initialized again.
    func initialized(context: Context)

    /// A lifecycle event that is triggered when the atom is updated.
    func updated(context: Context)

    /// A lifecycle event that is triggered when the atom is no longer watched and released.
    func released(context: Context)
}

public extension AtomEffect {
    func initialized(context: Context) {}
    func updated(context: Context) {}
    func released(context: Context) {}
}

```

## Sources/Atoms/Effect/UpdateEffect.swift

```
/// An atom effect that performs an arbitrary action when the atom is updated.
public struct UpdateEffect: AtomEffect {
    private let action: @MainActor () -> Void

    /// Creates an atom effect that performs the given action when the atom is updated.
    public init(perform action: @MainActor @escaping () -> Void) {
        self.action = action
    }

    /// A lifecycle event that is triggered when the atom is updated.
    public func updated(context: Context) {
        action()
    }
}

```

## Sources/Atoms/Effect/MergedEffect.swift

```
// Use type pack once it is available in iOS 17 or newer.
// MergedEffect<each Effect: AtomEffect>
/// An atom effect that merges multiple atom effects into one.
public struct MergedEffect: AtomEffect {
    private let initialized: @MainActor (Context) -> Void
    private let updated: @MainActor (Context) -> Void
    private let released: @MainActor (Context) -> Void

    /// Creates an atom effect that merges multiple atom effects into one.
    public init<each Effect: AtomEffect>(_ effect: repeat each Effect) {
        initialized = { @Sendable context in
            repeat (each effect).initialized(context: context)
        }
        updated = { @Sendable context in
            repeat (each effect).updated(context: context)
        }
        released = { @Sendable context in
            repeat (each effect).released(context: context)
        }
    }

    /// A lifecycle event that is triggered when the atom is first used and initialized,
    /// or once it is released and re-initialized again.
    public func initialized(context: Context) {
        initialized(context)
    }

    /// A lifecycle event that is triggered when the atom is updated.
    public func updated(context: Context) {
        updated(context)
    }

    /// A lifecycle event that is triggered when the atom is no longer watched and released.
    public func released(context: Context) {
        released(context)
    }
}

```

## Sources/Atoms/PropertyWrapper/WatchStateObject.swift

````
import SwiftUI

/// A property wrapper type that can watch the given atom conforms to ``ObservableObjectAtom``.
///
/// It starts watching the atom when the view accesses the ``wrappedValue``, and when the atom changes,
/// the view invalidates its appearance and recomputes the body.
///
/// See also ``Watch`` to have read-only access and ``WatchState`` to write value of ``StateAtom``.
/// The interface of this property wrapper follows `@StateObject`.
///
/// ## Example
///
/// ```swift
/// class Counter: ObservableObject {
///     @Published var count = 0
///
///     func plus(_ value: Int) {
///         count += value
///     }
/// }
///
/// struct CounterAtom: ObservableObjectAtom, Hashable {
///     func object(context: Context) -> Counter {
///         Counter()
///     }
/// }
///
/// struct CounterView: View {
///     @WatchStateObject(CounterAtom())
///     var counter
///
///     var body: some View {
///         VStack {
///             Text("Count: \(counter.count)")    // Read property, and start watching.
///             Stepper(value: $counter.count) {}  // Use the property as a binding
///             Button("+100") {
///                 counter.plus(100)              // Call the method to update.
///             }
///         }
///     }
/// }
/// ```
///
@propertyWrapper
public struct WatchStateObject<Node: ObservableObjectAtom>: DynamicProperty {
    /// A wrapper of the underlying observable object that can create bindings to
    /// its properties using dynamic member lookup.
    @dynamicMemberLookup
    @MainActor
    public struct Wrapper {
        private let object: Node.Produced

        /// Returns a binding to the resulting value of the given key path.
        ///
        /// - Parameter keyPath: A key path to a specific resulting value.
        ///
        /// - Returns: A new binding.
        public subscript<T>(dynamicMember keyPath: ReferenceWritableKeyPath<Node.Produced, T>) -> Binding<T> {
            Binding(
                get: { object[keyPath: keyPath] },
                set: { object[keyPath: keyPath] = $0 }
            )
        }

        fileprivate init(_ object: Node.Produced) {
            self.object = object
        }
    }

    private let atom: Node

    @ViewContext
    private var context

    /// Creates an instance with the atom to watch.
    public init(_ atom: Node, fileID: String = #fileID, line: UInt = #line) {
        self.atom = atom
        self._context = ViewContext(fileID: fileID, line: line)
    }

    /// The underlying observable object associated with the given atom.
    ///
    /// This property provides primary access to the value's data. However, you don't
    /// access ``wrappedValue`` directly. Instead, you use the property variable created
    /// with the `@WatchStateObject` attribute.
    /// Accessing this property starts watching the atom.
    #if compiler(>=6) || hasFeature(DisableOutwardActorInference)
        @MainActor
    #endif
    public var wrappedValue: Node.Produced {
        context.watch(atom)
    }

    /// A projection of the state object that creates bindings to its properties.
    ///
    /// Use the projected value to pass a binding value down a view hierarchy.
    /// To get the projected value, prefix the property variable with `$`.
    #if compiler(>=6) || hasFeature(DisableOutwardActorInference)
        @MainActor
    #endif
    public var projectedValue: Wrapper {
        Wrapper(wrappedValue)
    }
}

````

## Sources/Atoms/PropertyWrapper/ViewContext.swift

````
import SwiftUI

/// A property wrapper type that provides a context structure to read, watch, and otherwise
/// interact with atoms from views.
///
/// Through the provided context, the view can read, write, or perform other interactions with atoms.
/// If the view watches an atom through the context, the view invalidates its appearance and recompute
/// the body when the atom value updates.
///
/// - SeeAlso: ``AtomViewContext``
///
/// ## Example
///
/// ```swift
/// struct CounterView: View {
///     @ViewContext
///     var context
///
///     var body: some View {
///         VStack {
///             Text("Count: \(context.watch(CounterAtom()))")  // Read value, and start watching.
///             Button("Increment") {
///                 context[CounterAtom()] += 1                 // Mutation which means simultaneous read-write access.
///             }
///             Button("Reset") {
///                 context.reset(CounterAtom())                // Reset to default value.
///             }
///         }
///     }
/// }
/// ```
///
@propertyWrapper
public struct ViewContext: DynamicProperty {
    private let file: StaticString
    private let location: SourceLocation

    @Environment(\.store)
    private var _store

    @StateObject
    private var state = State()

    /// Creates a view context.
    public init(file: StaticString = #file, fileID: String = #fileID, line: UInt = #line) {
        self.file = file
        self.location = SourceLocation(fileID: fileID, line: line)
    }

    /// The underlying view context to interact with atoms.
    ///
    /// This property provides primary access to the view context. However you don't
    /// access ``wrappedValue`` directly.
    /// Instead, you use the property variable created with the `@ViewContext` attribute.
    #if compiler(>=6) || hasFeature(DisableOutwardActorInference)
        @MainActor
    #endif
    public var wrappedValue: AtomViewContext {
        AtomViewContext(
            store: store,
            subscriber: Subscriber(state.subscriberState),
            subscription: Subscription(location: location) { [weak state] in
                state?.objectWillChange.send()
            }
        )
    }
}

private extension ViewContext {
    @MainActor
    final class State: ObservableObject {
        let subscriberState = SubscriberState()
    }

    @MainActor
    var store: StoreContext {
        guard let _store else {
            assertionFailure(
                """
                [Atoms]
                There is no store provided on the current view tree.
                Make sure that this application has an `AtomRoot` as a root ancestor of any view.

                ```
                struct ExampleApp: App {
                    var body: some Scene {
                        WindowGroup {
                            AtomRoot {
                                ExampleView()
                            }
                        }
                    }
                }
                ```
                If for some reason the view tree is formed that does not inherit from `EnvironmentValues`,
                consider using `AtomScope` to pass it.
                That happens when using SwiftUI view wrapped with `UIHostingController`.

                ```
                struct ExampleView: View {
                    @ViewContext
                    var context

                    var body: some View {
                        UIViewWrappingView {
                            AtomScope(inheriting: context) {
                                WrappedView()
                            }
                        }
                    }
                }
                ```
                The modal screen presented by the `.sheet` modifier or etc, inherits from the environment values,
                but only in iOS14, there is a bug where the environment values will be dismantled during it is
                dismissing. This also can be avoided by using `AtomScope` to explicitly inherit from it.

                ```
                .sheet(isPresented: ...) {
                    AtomScope(inheriting: context) {
                        ExampleView()
                    }
                }
                ```
                """,
                file: file,
                line: location.line
            )

            // Returns an ephemeral instance just to not crash in `-O` builds.
            return StoreContext(
                store: AtomStore(),
                scopeKey: ScopeKey(token: ScopeKey.Token()),
                inheritedScopeKeys: [:],
                observers: [],
                scopedObservers: [],
                overrides: [:],
                scopedOverrides: [:]
            )
        }

        return _store
    }
}

````

## Sources/Atoms/PropertyWrapper/WatchState.swift

````
import SwiftUI

/// A property wrapper type that can watch and read-write access to the given atom conforms
/// to ``StateAtom``.
///
/// It starts watching the atom when the view accesses the ``wrappedValue``, and when the atom changes,
/// the view invalidates its appearance and recomputes the body. However, if only write access is
/// performed, it doesn't start watching.
///
/// See also ``Watch`` to have read-only access and ``WatchStateObject`` to receive updates of
/// ``ObservableObjectAtom``.
/// The interface of this property wrapper follows `@State`.
///
/// ## Example
///
/// ```swift
/// struct CounterView: View {
///     @WatchState(CounterAtom())
///     var count
///
///     var body: some View {
///         VStack {
///             Text("Count: \(count)")    // Read value, and start watching.
///             Stepper(value: $count) {}  // Use as a binding
///             Button("+100") {
///                 count += 100           // Mutation which means simultaneous read-write access.
///             }
///         }
///     }
/// }
/// ```
///
@propertyWrapper
public struct WatchState<Node: StateAtom>: DynamicProperty {
    private let atom: Node

    @ViewContext
    private var context

    /// Creates an instance with the atom to watch.
    public init(_ atom: Node, fileID: String = #fileID, line: UInt = #line) {
        self.atom = atom
        self._context = ViewContext(fileID: fileID, line: line)
    }

    /// The underlying value associated with the given atom.
    ///
    /// This property provides primary access to the value's data. However, you don't
    /// access ``wrappedValue`` directly. Instead, you use the property variable created
    /// with the `@WatchState` attribute.
    /// Accessing to the getter of this property starts watching the atom, but doesn't
    /// by setting a new value.
    #if compiler(>=6) || hasFeature(DisableOutwardActorInference)
        @MainActor
    #endif
    public var wrappedValue: Node.Produced {
        get { context.watch(atom) }
        nonmutating set { context.set(newValue, for: atom) }
    }

    /// A binding to the atom value.
    ///
    /// Use the projected value to pass a binding value down a view hierarchy.
    /// To get the ``projectedValue``, prefix the property variable with `$`.
    /// Accessing this property itself does not start watching the atom, but does when
    /// the view accesses to the getter of the binding.
    #if compiler(>=6) || hasFeature(DisableOutwardActorInference)
        @MainActor
    #endif
    public var projectedValue: Binding<Node.Produced> {
        context.binding(atom)
    }
}

````

## Sources/Atoms/PropertyWrapper/Watch.swift

````
import SwiftUI

/// A property wrapper type that can watch and read-only access to the given atom.
///
/// It starts watching the atom when the view accesses the ``wrappedValue``, and when the atom value
/// changes, the view invalidates its appearance and recomputes the body.
///
/// See also ``WatchState`` to write value of ``StateAtom`` and ``WatchStateObject`` to receive updates of
/// ``ObservableObjectAtom``.
///
/// ## Example
///
/// ```swift
/// struct CountDisplay: View {
///     @Watch(CounterAtom())
///     var count
///
///     var body: some View {
///         Text("Count: \(count)")  // Read value, and start watching.
///     }
/// }
/// ```
///
@propertyWrapper
public struct Watch<Node: Atom>: DynamicProperty {
    private let atom: Node

    @ViewContext
    private var context

    /// Creates an instance with the atom to watch.
    public init(_ atom: Node, fileID: String = #fileID, line: UInt = #line) {
        self.atom = atom
        self._context = ViewContext(fileID: fileID, line: line)
    }

    /// The underlying value associated with the given atom.
    ///
    /// This property provides primary access to the value's data. However, you don't
    /// access ``wrappedValue`` directly. Instead, you use the property variable created
    /// with the `@Watch` attribute.
    /// Accessing this property starts watching the atom.
    #if compiler(>=6) || hasFeature(DisableOutwardActorInference)
        @MainActor
    #endif
    public var wrappedValue: Node.Produced {
        context.watch(atom)
    }
}

````
