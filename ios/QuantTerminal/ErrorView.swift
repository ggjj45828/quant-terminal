import SwiftUI

struct ErrorView: View {
    let message: String
    let url: String
    let onRetry: () -> Void
    let onSettings: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 52))
                .foregroundColor(Color(hex: "#8B5CF6"))

            Text("连接不上服务器")
                .font(.title3.weight(.semibold))
                .foregroundColor(.white)

            Text(message)
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.65))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 36)

            Text(url)
                .font(.caption.monospaced())
                .foregroundColor(.white.opacity(0.4))
                .padding(.horizontal, 36)

            VStack(spacing: 12) {
                Button(action: onRetry) {
                    Text("重试")
                        .font(.body.weight(.semibold))
                        .frame(maxWidth: .infinity)
                        .frame(height: 46)
                        .background(Color(hex: "#8B5CF6"))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }

                Button(action: onSettings) {
                    Text("修改服务器地址")
                        .font(.body)
                        .frame(maxWidth: .infinity)
                        .frame(height: 46)
                        .background(Color.white.opacity(0.1))
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
            }
            .padding(.horizontal, 36)
            .padding(.top, 8)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

#Preview {
    ErrorView(
        message: "连不上服务器。请确认服务已启动、地址填对。",
        url: "http://192.168.1.100:3018",
        onRetry: {}, onSettings: {}
    )
}
