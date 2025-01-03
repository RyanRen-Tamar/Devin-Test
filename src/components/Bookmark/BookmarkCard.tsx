import React from 'react';
import { Card } from "../ui/card";
import { Button } from "../ui/button";
import { MoreHorizontal, Star } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

interface BookmarkCardProps {
  title: string;
  date: string;
  isTemplate?: boolean;
  onSaveAsTemplate?: () => void;
}

const BookmarkCard: React.FC<BookmarkCardProps> = ({
  title,
  date,
  isTemplate = false,
  onSaveAsTemplate,
}) => {
  return (
    <Card className="p-4 hover:shadow-lg transition-all duration-200 hover:-translate-y-1">
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <h3 className="font-medium text-lg">{title}</h3>
          <p className="text-sm text-gray-500 mt-1">{date}</p>
        </div>
        <div className="flex items-center gap-2">
          {isTemplate && (
            <Star className="text-blue-500" size={20} />
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={onSaveAsTemplate}>
                存储为模板
              </DropdownMenuItem>
              <DropdownMenuItem>
                编辑
              </DropdownMenuItem>
              <DropdownMenuItem className="text-red-600">
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </Card>
  );
};

export default BookmarkCard;
