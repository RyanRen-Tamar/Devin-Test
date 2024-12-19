import { type FC } from 'react'
import { Card, CardContent } from "../../components/ui/card"
import { Button } from "../../components/ui/button"
import { FileText, MoreVertical, Edit, Trash } from 'lucide-react'
import { Avatar, AvatarFallback, AvatarImage } from "../../components/ui/avatar"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../../components/ui/dropdown-menu"

interface ReportCardProps {
  title: string
  author: string
  date: string
  content: string
  avatarUrl?: string
  avatarFallback: string
  onEdit?: () => void
  onDelete?: () => void
}

export const ReportCard: FC<ReportCardProps> = ({
  title,
  author,
  date,
  content,
  avatarUrl,
  avatarFallback,
  onEdit,
  onDelete
}) => {
  return (
    <Card className="hover:shadow-md transition-shadow cursor-pointer rounded-lg">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <Avatar className="h-8 w-8">
              <AvatarImage src={avatarUrl} />
              <AvatarFallback>{avatarFallback}</AvatarFallback>
            </Avatar>
            <div>
              <h3 className="text-sm font-medium">{title}</h3>
              <p className="text-xs text-gray-500">{author} • {date}</p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={onEdit}>
                <Edit className="h-4 w-4 mr-2" />
                编辑
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onDelete} className="text-red-600">
                <Trash className="h-4 w-4 mr-2" />
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="mt-3">
          <p className="text-sm text-gray-600 line-clamp-3">
            {content}
          </p>
        </div>
        <div className="mt-4 flex items-center gap-2">
          <FileText className="h-4 w-4 text-gray-500" />
          <span className="text-xs text-gray-500">完整报告</span>
        </div>
      </CardContent>
    </Card>
  )
}
