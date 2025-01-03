import React, { useState } from 'react';
import BookmarkCard from './BookmarkCard';
import TemplateDialog from './TemplateDialog';

interface Bookmark {
  id: number;
  title: string;
  date: string;
  isTemplate: boolean;
}

const BookmarkGrid: React.FC = () => {
  const [isTemplateDialogOpen, setIsTemplateDialogOpen] = useState(false);
  const [selectedBookmark, setSelectedBookmark] = useState<Bookmark | null>(null);

  // Mock data
  const bookmarks: Bookmark[] = [
    { id: 1, title: "项目会议记录", date: "2024-03-20", isTemplate: false },
    { id: 2, title: "周报模板", date: "2024-03-19", isTemplate: true },
    { id: 3, title: "任务清单", date: "2024-03-18", isTemplate: false },
    { id: 4, title: "产品规划", date: "2024-03-17", isTemplate: false },
    { id: 5, title: "日报模板", date: "2024-03-16", isTemplate: true },
    { id: 6, title: "团队会议纪要", date: "2024-03-15", isTemplate: false },
  ];

  const handleSaveAsTemplate = (bookmark: Bookmark) => {
    setSelectedBookmark(bookmark);
    setIsTemplateDialogOpen(true);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {bookmarks.map((bookmark) => (
        <BookmarkCard
          key={bookmark.id}
          title={bookmark.title}
          date={bookmark.date}
          isTemplate={bookmark.isTemplate}
          onSaveAsTemplate={() => handleSaveAsTemplate(bookmark)}
        />
      ))}

      <TemplateDialog
        open={isTemplateDialogOpen}
        onOpenChange={setIsTemplateDialogOpen}
        bookmark={selectedBookmark}
      />
    </div>
  );
};

export default BookmarkGrid;
