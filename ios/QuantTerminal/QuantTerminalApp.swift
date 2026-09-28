import SwiftUI
import WebKit
import UIKit

// ============================================================
//  Quant Terminal · iOS 原生壳
//
//  用 WKWebView 承载已部署好的 Quant Terminal 网页,
//  外面包一层原生壳: 全屏沉浸式、下拉刷新、面容解锁、
//  服务器地址配置、网络异常兜底页。
//
//  ⚠️ 使用前必改: Config.swift 里的 defaultServerURL
// ============================================================

@main
struct QuantTerminalApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var settings = AppSettings.shared
    @StateObject private var lockManager = LockManager.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(settings)
                .environmentObject(lockManager)
                .preferredColorScheme(.dark)   // 项目为暗色终端风格
        }
    }
}

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        // 关闭 WebView 的键盘自动插入工具栏, 更贴近原生
        NotificationCenter.default.addObserver(
            forName: UIApplication.didBecomeActiveNotification,
            object: nil, queue: .main
        ) { _ in
            LockManager.shared.checkLockOnResume()
        }
        return true
    }

    // 横竖屏: 允许旋转, 由页面自己适配
    func application(
        _ application: UIApplication,
        supportedInterfaceOrientationsFor window: UIWindow?
    ) -> UIInterfaceOrientationMask {
        .all
    }
}

struct RootView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var lockManager: LockManager

    var body: some View {
        ZStack {
            if lockManager.isLocked && settings.biometricLockEnabled {
                LockView()
                    .environmentObject(lockManager)
            } else {
                WebContainerView()
                    .environmentObject(settings)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: lockManager.isLocked)
    }
}
