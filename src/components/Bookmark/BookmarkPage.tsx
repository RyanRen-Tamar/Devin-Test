import React from 'react';
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";
import BookmarkGrid from './BookmarkGrid';
import BookmarkFilter from './BookmarkFilter';

const BookmarkPage: React.FC = () => {
  return (
    <div className="flex h-full">
      {/* Calendar Section */}
      <div className="w-64 border-r bg-gray-50 p-4">
        <h2 className="text-lg font-semibold mb-4">日历</h2>
        {/* Calendar component will be integrated here */}
        <div className="bg-white rounded-lg p-4 shadow-sm">
          <div className="grid grid-cols-7 gap-1 text-center text-sm mb-2">
            <div>日</div>
            <div>一</div>
            <div>二</div>
            <div>三</div>
            <div>四</div>
            <div>五</div>
            <div>六</div>
          </div>
          {/* Calendar grid placeholder */}
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: 31 }, (_, i) => (
              <div
                key={i}
                className="aspect-square flex items-center justify-center text-sm hover:bg-gray-100 rounded cursor-pointer"
              >
                {i + 1}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header Section */}
        <div className="flex items-center justify-between p-6 border-b">
          <h1 className="text-2xl font-semibold">我的收藏</h1>
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
              <Input
                className="pl-10 w-[300px]"
                placeholder="搜索收藏..."
              />
            </div>
          </div>
        </div>

        {/* Filter Section */}
        <BookmarkFilter />

        {/* Content Section */}
        <div className="flex-1 p-6 overflow-auto">
          <BookmarkGrid />
        </div>
      </div>
    </div>
  );
};

export default BookmarkPage;
