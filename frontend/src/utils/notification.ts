// 与 utils/toast.ts 同样的 D4 按需引入模式：手动引入 ElNotification 及其样式，
// 主包不背整套 element-plus。全站从这一个出口导入。
import { ElNotification } from 'element-plus'
import 'element-plus/es/components/notification/style/css'

export { ElNotification }
