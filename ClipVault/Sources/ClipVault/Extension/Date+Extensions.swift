import Foundation

extension Date {
    /// 相对时间描述（中文）
    var relativeTimeDescription: String {
        let now = Date()
        let interval = now.timeIntervalSince(self)

        if interval < 0 {
            return "刚刚"
        }

        let seconds = Int(interval)
        let minutes = seconds / 60
        let hours = minutes / 60
        let days = hours / 24

        switch seconds {
        case 0..<10:
            return "刚刚"
        case 10..<60:
            return "\(seconds) 秒前"
        default:
            break
        }

        switch minutes {
        case 1..<60:
            return "\(minutes) 分钟前"
        default:
            break
        }

        switch hours {
        case 1..<24:
            return "\(hours) 小时前"
        default:
            break
        }

        switch days {
        case 1:
            return "昨天"
        case 2..<7:
            return "\(days) 天前"
        default:
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "zh_CN")
            formatter.dateFormat = "MM-dd HH:mm"
            return formatter.string(from: self)
        }
    }

    /// 简短时间格式
    var shortTimeString: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_CN")
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: self)
    }

    /// 完整日期时间格式
    var fullDateTimeString: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_CN")
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return formatter.string(from: self)
    }
}
