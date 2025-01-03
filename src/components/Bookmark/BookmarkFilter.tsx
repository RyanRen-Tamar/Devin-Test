import React from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";

interface BookmarkFilterProps {
  onFilterChange?: (filter: string) => void;
  onSortChange?: (sort: string) => void;
}

const BookmarkFilter: React.FC<BookmarkFilterProps> = ({
  onFilterChange,
  onSortChange,
}) => {
  return (
    <div className="flex items-center gap-4 p-4 border-b bg-gray-50">
      <Select defaultValue="all" onValueChange={onFilterChange}>
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="全部" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部</SelectItem>
          <SelectItem value="bookmark">收藏</SelectItem>
          <SelectItem value="template">模板</SelectItem>
        </SelectContent>
      </Select>

      <Select defaultValue="newest" onValueChange={onSortChange}>
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="排序方式" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="newest">最新添加</SelectItem>
          <SelectItem value="oldest">最早添加</SelectItem>
          <SelectItem value="name">名称排序</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
};

export default BookmarkFilter;
