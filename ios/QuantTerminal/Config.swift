import Foundation
import SwiftUI

// ============================================================
//  服务器地址配置
//
//  ⚠️ 改成你自己的服务地址:
//    - 连家里的 NAS: http://192.168.1.100:3018  (或极空间远程访问地址)
//    - 连云服务器:   http://你的公网IP:3018      (建议配 HTTPS 域名)
//
//  首次启动 App 后也可以在「设置」里改, 会存到本机。
// ============================================================

enum Config {
    /// 默认服务器地址(改成你自己的)
    static let defaultServerURL = "http://192.168.1.100:3018"

    /// 允许的本地/局域网兜底地址(检测用)
    static let fallbackURLs: [String] = []

    /// App 名称
    static let appName = "Quant Terminal"

    /// 用户代理后缀, 便于后端识别 iOS 客户端(可选)
    static let userAgentSuffix = " QuantTerminal-iOS/1.0"
}

final class AppSettings: ObservableObject {
    static let shared = AppSettings()

    private let urlKey = "qt.serverURL"
    private let lockKey = "qt.biometricLock"
    private let pullKey = "qt.pullToRefresh"

    @Published var serverURL: String {
        didSet { UserDefaults.standard.set(serverURL, forKey: urlKey) }
    }

    @Published var biometricLockEnabled: Bool {
        didSet { UserDefaults.standard.set(biometricLockEnabled, forKey: lockKey) }
    }

    @Published var pullToRefreshEnabled: Bool {
        didSet { UserDefaults.standard.set(pullToRefreshEnabled, forKey: pullKey) }
    }

    init() {
        let saved = UserDefaults.standard.string(forKey: urlKey)
        self.serverURL = (saved?.isEmpty == false) ? saved! : Config.defaultServerURL
        self.biometricLockEnabled = UserDefaults.standard.bool(forKey: lockKey)
        self.pullToRefreshEnabled = UserDefaults.standard.object(forKey: pullKey) as? Bool ?? true
    }

    /// 规范化地址: 自动补 http://, 去掉结尾斜杠
    var normalizedURL: String {
        var s = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        if !s.hasPrefix("http://") && !s.hasPrefix("https://") {
            s = "http://" + s
        }
        while s.hasSuffix("/") { s.removeLast() }
        return s
    }

    func reset() {
        serverURL = Config.defaultServerURL
        biometricLockEnabled = false
        pullToRefreshEnabled = true
    }
}
