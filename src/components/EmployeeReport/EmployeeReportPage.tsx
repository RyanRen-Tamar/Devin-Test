import { type FC } from 'react'
import { Input } from "../../components/ui/input"
import { Button } from "../../components/ui/button"
import { Search, Filter, Plus } from 'lucide-react'
import { ReportCard } from './ReportCard'

export const EmployeeReportPage: FC = () => {
  return (
    <div className="p-4 md:p-8">
      {/* Header */}
      <header className="mb-6 md:mb-8">
        <h1 className="text-xl md:text-2xl font-semibold text-gray-900">员工汇报</h1>
        <p className="text-sm md:text-base text-gray-600">查看和管理员工汇报</p>
      </header>

      {/* Search and Filter Bar */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex-1 relative">
          <Input
            placeholder="搜索汇报..."
            className="pl-10"
          />
          <Search className="h-4 w-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500" />
        </div>
        <Button variant="outline" size="icon" className="rounded-lg">
          <Filter className="h-4 w-4" />
        </Button>
        <Button className="rounded-lg">
          <Plus className="h-4 w-4 mr-2" />
          新建汇报
        </Button>
      </div>

      {/* Reports Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ReportCard
          title="周报告：项目进展"
          author="张三"
          date="2024/01/20"
          content="本周完成了用户界面的设计和实现，包括主页布局、导航栏和响应式适配..."
          avatarUrl="https://github.com/shadcn.png"
          avatarFallback="JD"
          onEdit={() => console.log('Edit report 1')}
          onDelete={() => console.log('Delete report 1')}
        />

        <ReportCard
          title="月度总结：研发进展"
          author="李四"
          date="2024/01/19"
          content="本月重点推进了后端API开发，完成了用户认证系统和数据库优化..."
          avatarUrl="https://github.com/shadcn.png"
          avatarFallback="LW"
          onEdit={() => console.log('Edit report 2')}
          onDelete={() => console.log('Delete report 2')}
        />

        <ReportCard
          title="季度汇报：产品规划"
          author="王五"
          date="2024/01/18"
          content="第一季度重点关注用户体验优化，计划推出新的功能模块..."
          avatarUrl="https://github.com/shadcn.png"
          avatarFallback="WX"
          onEdit={() => console.log('Edit report 3')}
          onDelete={() => console.log('Delete report 3')}
        />
      </div>
    </div>
  )
}

export default EmployeeReportPage
