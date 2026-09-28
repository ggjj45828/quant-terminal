// ============================================================
//  品牌配置 —— 想换成你自己的名字, 只改这个文件即可
// ============================================================
//  侧栏标题、浏览器标签页标题、favicon、推送消息标题都会读这里的常量。
//  改完重新构建前端 (docker compose up --build) 即生效。
//
//  改名的三个位置 (本文件改完就够, 无需动其他代码):
//    1. BRAND_NAME     —— 侧栏显示的名字
//    2. BRAND_TITLE    —— 浏览器标签页标题
//    3. BRAND_TAGLINE  —— 签名/副标题一句话
//
//  想换配色改 BRAND_COLOR 即可 (侧栏 logo / 发光线 / 主题色都跟着变)。
// ============================================================

/** 侧栏显示的产品名 (建议 2~4 个词, 太长会撑爆侧栏) */
export const BRAND_NAME = 'Quant Terminal'

/** 浏览器标签页 <title> */
export const BRAND_TITLE = 'Quant Terminal · 量化工作台'

/** 副标题 / 签名一句话 */
export const BRAND_TAGLINE = 'A-SHARE · SIGNAL TERMINAL'

/** 品牌主色 (logo / 侧栏发光线 / 主题色) */
export const BRAND_COLOR = '#8B5CF6'

/** 推送消息(飞书/钉钉等)的标题前缀 */
export const BRAND_PUSH_PREFIX = 'Quant Terminal'
