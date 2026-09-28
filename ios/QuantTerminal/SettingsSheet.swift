import SwiftUI

struct SettingsSheet: View {
    @EnvironmentObject var settings: AppSettings
    @Environment(\.dismiss) private var dismiss

    @State private var urlText: String = ""
    @State private var showResetConfirm = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("服务器地址")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        TextField("http://192.168.1.100:3018", text: $urlText)
                            .keyboardType(.URL)
                            .autocapitalization(.none)
                            .autocorrectionDisabled()
                            .font(.body.monospaced())
                        Text("连家里的 NAS 填内网 IP；连云服务器填公网地址。")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 4)

                    Button("保存并重新加载") {
                        settings.serverURL = urlText
                        NotificationCenter.default.post(name: .reloadWebView, object: nil)
                        dismiss()
                    }
                } header: {
                    Text("连接")
                }

                Section {
                    Toggle("下拉刷新", isOn: $settings.pullToRefreshEnabled)
                    Toggle("面容/指纹解锁", isOn: $settings.biometricLockEnabled)
                } header: {
                    Text("交互")
                } footer: {
                    Text("开启后每次切回 App 需要验证身份，保护你的持仓与策略数据。")
                }

                Section {
                    Button("恢复默认设置", role: .destructive) {
                        showResetConfirm = true
                    }
                }

                Section {
                    HStack {
                        Text("版本")
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.secondary)
                    }
                } header: {
                    Text("关于")
                }
            }
            .navigationTitle("设置")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("完成") { dismiss() }
                }
            }
            .onAppear { urlText = settings.serverURL }
            .alert("恢复默认设置？", isPresented: $showResetConfirm) {
                Button("取消", role: .cancel) {}
                Button("恢复", role: .destructive) {
                    settings.reset()
                    urlText = settings.serverURL
                    NotificationCenter.default.post(name: .reloadWebView, object: nil)
                }
            } message: {
                Text("服务器地址和所有偏好将恢复默认。")
            }
        }
    }
}

#Preview {
    SettingsSheet().environmentObject(AppSettings.shared)
}
