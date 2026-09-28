import SwiftUI
import WebKit
import UIKit

// ============================================================
//  WebView 容器 —— 全屏沉浸式 + 下拉刷新 + 加载状态 + 错误兜底
// ============================================================

struct WebContainerView: View {
    @EnvironmentObject var settings: AppSettings
    @State private var showSettings = false
    @State private var isLoading = true
    @State private var loadError: String?
    @State private var progress: Double = 0
    @State private var canGoBack = false

    var body: some View {
        ZStack(alignment: .top) {
            WebViewRepresentable(
                url: URL(string: settings.normalizedURL)!,
                isLoading: $isLoading,
                loadError: $loadError,
                progress: $progress,
                canGoBack: $canGoBack,
                pullToRefresh: settings.pullToRefreshEnabled
            )
            // 关键: 忽略安全区, 实现真正全屏(内容延伸到刘海下方)
            .ignoresSafeArea(edges: .all)
            .statusBarHidden(false)

            // 顶部加载进度条
            if isLoading {
                ProgressView(value: progress, total: 1.0)
                    .progressViewStyle(.linear)
                    .tint(Color(hex: "#8B5CF6"))
                    .frame(height: 2)
                    .padding(.top, safeAreaTop)
                    .transition(.opacity)
            }

            // 悬浮设置按钮(长按可拖动, 这里简单放右上角)
            VStack {
                HStack {
                    Spacer()
                    Button {
                        showSettings = true
                    } label: {
                        Image(systemName: "gearshape.fill")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundColor(.white.opacity(0.75))
                            .frame(width: 34, height: 34)
                            .background(.ultraThinMaterial, in: Circle())
                    }
                    .padding(.trailing, 14)
                    .padding(.top, safeAreaTop + 6)
                }
                Spacer()
            }

            // 加载失败兜底页
            if let err = loadError {
                ErrorView(message: err, url: settings.normalizedURL) {
                    loadError = nil
                    isLoading = true
                    NotificationCenter.default.post(name: .reloadWebView, object: nil)
                } onSettings: {
                    showSettings = true
                }
                .background(Color(hex: "#0B0B12"))
                .ignoresSafeArea()
            }
        }
        .sheet(isPresented: $showSettings) {
            SettingsSheet()
                .environmentObject(settings)
        }
    }

    private var safeAreaTop: CGFloat {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first?.windows.first?.safeAreaInsets.top ?? 44
    }
}

// MARK: - UIViewRepresentable

struct WebViewRepresentable: UIViewRepresentable {
    let url: URL
    @Binding var isLoading: Bool
    @Binding var loadError: String?
    @Binding var progress: Double
    @Binding var canGoBack: Bool
    let pullToRefresh: Bool

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator

        // 允许手势返回
        webView.allowsBackForwardNavigationGestures = true
        // 滚动回弹关闭, 更像原生
        webView.scrollView.bounces = pullToRefresh
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        // 深色背景, 避免加载白闪
        webView.backgroundColor = UIColor(hex: "#0B0B12")
        webView.isOpaque = false
        webView.scrollView.backgroundColor = UIColor(hex: "#0B0B12")
        // UA 加后缀便于后端识别
        webView.customUserAgent = (webView.value(forKey: "userAgent") as? String ?? "") + Config.userAgentSuffix

        // 下拉刷新
        if pullToRefresh {
            let refresh = UIRefreshControl()
            refresh.tintColor = UIColor(hex: "#8B5CF6")
            refresh.addTarget(context.coordinator, action: #selector(Coordinator.handleRefresh(_:)), for: .valueChanged)
            webView.scrollView.refreshControl = refresh
        }

        context.coordinator.webView = webView
        context.coordinator.load(url)

        // 监听外部重加载请求
        NotificationCenter.default.addObserver(
            context.coordinator,
            selector: #selector(Coordinator.handleReloadNotification),
            name: .reloadWebView, object: nil
        )
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        // 地址变更时重新加载
        if context.coordinator.currentURL != url {
            context.coordinator.load(url)
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        var parent: WebViewRepresentable
        var webView: WKWebView?
        var currentURL: URL?
        private var isFirstLoad = true

        init(_ parent: WebViewRepresentable) { self.parent = parent }

        func load(_ url: URL) {
            currentURL = url
            parent.loadError = nil
            parent.isLoading = true
            webView?.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30))
        }

        @objc func handleRefresh(_ sender: UIRefreshControl) {
            if let url = currentURL { load(url) }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { sender.endRefreshing() }
        }

        @objc func handleReloadNotification() {
            if let url = currentURL { load(url) }
        }

        // 页面开始加载
        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.isLoading = true
            parent.loadError = nil
        }

        // 加载完成
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.isLoading = false
            parent.progress = 1
            parent.canGoBack = webView.canGoBack
        }

        // 加载失败
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            handleError(error)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            handleError(error)
        }

        private func handleError(_ error: Error) {
            let nsErr = error as NSError
            // 忽略加载被取消等情况
            if nsErr.code == NSURLErrorCancelled { return }
            parent.isLoading = false
            parent.loadError = Self.friendlyMessage(for: nsErr)
        }

        static func friendlyMessage(for err: NSError) -> String {
            switch err.code {
            case NSURLErrorCannotConnectToHost, NSURLErrorCannotFindHost:
                return "连不上服务器。请确认服务已启动、地址填对，且手机与服务器在同一网络。"
            case NSURLErrorTimedOut:
                return "连接超时。服务器可能没开机，或网络不通。"
            case NSURLErrorNotConnectedToInternet:
                return "手机没有联网。请检查 Wi-Fi 或蜂窝网络。"
            case NSURLErrorSecureConnectionFailed, NSURLErrorServerCertificateUntrusted:
                return "HTTPS 证书校验失败。若用的是自签证书，需先信任该证书。"
            default:
                return "加载失败：\(err.localizedDescription)（错误码 \(err.code)）"
            }
        }

        // 允许新窗口(target=_blank)在当前页打开
        func webView(_ webView: WKWebView,
                     createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction,
                     windowFeatures: WKWindowFeatures) -> WKWebView? {
            if navigationAction.targetFrame == nil {
                webView.load(navigationAction.request)
            }
            return nil
        }

        // JS 弹窗交给原生处理
        func webView(_ webView: WKWebView,
                     runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping () -> Void) {
            let ac = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            ac.addAction(UIAlertAction(title: "好", style: .default) { _ in completionHandler() })
            topViewController()?.present(ac, animated: true)
        }

        func webView(_ webView: WKWebView,
                     runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping (Bool) -> Void) {
            let ac = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            ac.addAction(UIAlertAction(title: "取消", style: .cancel) { _ in completionHandler(false) })
            ac.addAction(UIAlertAction(title: "确定", style: .default) { _ in completionHandler(true) })
            topViewController()?.present(ac, animated: true)
        }

        private func topViewController() -> UIViewController? {
            UIApplication.shared.connectedScenes
                .compactMap { $0 as? UIWindowScene }
                .flatMap { $0.windows }
                .first(where: { $0.isKeyWindow })?.rootViewController
        }
    }
}

extension Notification.Name {
    static let reloadWebView = Notification.Name("qt.reloadWebView")
}
