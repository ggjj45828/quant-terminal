import SwiftUI
import LocalAuthentication
import UIKit

// ============================================================
//  面容 ID / 触控 ID 解锁
//  开启后, App 从后台切回时需验证身份
// ============================================================

final class LockManager: ObservableObject {
    static let shared = LockManager()

    @Published var isLocked = false

    private init() {}

    /// App 回到前台时调用
    func checkLockOnResume() {
        guard AppSettings.shared.biometricLockEnabled else { return }
        isLocked = true
        authenticate()
    }

    func authenticate() {
        let context = LAContext()
        var error: NSError?
        let reason = "验证身份以进入 Quant Terminal"

        if context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) {
            context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: reason) { success, _ in
                DispatchQueue.main.async {
                    if success { self.isLocked = false }
                }
            }
        } else {
            // 设备不支持生物识别(已设密码时仍走系统密码)
            DispatchQueue.main.async { self.isLocked = false }
        }
    }
}

struct LockView: View {
    @EnvironmentObject var lock: LockManager

    var body: some View {
        ZStack {
            Color(hex: "#0B0B12").ignoresSafeArea()

            VStack(spacing: 24) {
                Image(systemName: "lock.fill")
                    .font(.system(size: 46))
                    .foregroundColor(Color(hex: "#8B5CF6"))

                Text("Quant Terminal 已锁定")
                    .font(.headline)
                    .foregroundColor(.white)

                Button {
                    lock.authenticate()
                } label: {
                    Text("验证身份")
                        .font(.body.weight(.semibold))
                        .frame(width: 180, height: 46)
                        .background(Color(hex: "#8B5CF6"))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
            }
        }
        .onAppear { lock.authenticate() }
    }
}

#Preview {
    LockView().environmentObject(LockManager.shared)
}
