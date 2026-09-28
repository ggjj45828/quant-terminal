// 原创 logo:圆角终端框 + 上升折线 + 递增成交量柱
//
// 概念:
//   - 外层圆角方框:终端 / 面板 / 工作台边界
//   - 上升折线 + 箭头:趋势向上,直接的 quant 语义
//   - 底部三根递增柱:成交量 / 动能逐级放大
//
// 用 currentColor,继承父级 color 设定,方便切换品牌色。
// 想换成别的造型,只改本文件的 <svg> 内容即可,其他代码不受影响。
import { BRAND_NAME } from '@/lib/brand'

interface LogoProps {
  className?: string
  size?: number
  style?: React.CSSProperties
}

export function Logo({ className, size = 32, style }: LogoProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      width={size}
      height={size}
      fill="none"
      className={className}
      style={style}
      role="img"
      aria-label={BRAND_NAME}
    >
      {/* 外层圆角终端框 */}
      <rect
        x="3" y="3" width="26" height="26" rx="7"
        stroke="currentColor"
        strokeWidth="2"
        strokeOpacity="0.35"
      />
      {/* 上升折线 */}
      <path
        d="M8 19 L13 13.5 L17 16 L22.5 9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* 折线末端箭头(开口,指向右上) */}
      <path
        d="M17.5 9 L22.5 9 L22.5 14"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* 底部递增柱 — 动能逐级放大 */}
      <rect x="8" y="24" width="3" height="3" rx="0.75" fill="currentColor" fillOpacity="0.55" />
      <rect x="14.5" y="22" width="3" height="5" rx="0.75" fill="currentColor" fillOpacity="0.7" />
      <rect x="21" y="19.5" width="3" height="7.5" rx="0.75" fill="currentColor" />
    </svg>
  )
}
