"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getCourses, getSharedCourses, createCourse, reorderCourses, type CourseItem } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { CourseList } from "@/components/course-list";
import { AddForm } from "@/components/add-form";

export function HomePage() {
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [sharedCourses, setSharedCourses] = useState<CourseItem[]>([]);

  const refresh = useCallback(async () => {
    const [own, shared] = await Promise.all([getCourses(), getSharedCourses()]);
    setCourses(own);
    setSharedCourses(shared);
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function handleAdd(title: string) {
    await createCourse(title);
    await refresh();
    window.dispatchEvent(new Event("sidebar-refresh"));
  }

  async function handleReorder(ids: string[]) {
    setCourses((prev) => ids.map((id) => prev.find((c) => c.id === id)!));
    await reorderCourses(ids);
    window.dispatchEvent(new Event("sidebar-refresh"));
  }

  return (
    <section>
      <h1 className="text-2xl font-bold mb-4">Courses</h1>
      <CourseList courses={courses} onReorder={handleReorder} />
      <AddForm onAdd={handleAdd} placeholder="New course title…" />

      {sharedCourses.length > 0 && (
        <>
          <h2 className="text-xl font-bold mt-8 mb-4">Shared courses</h2>
          {sharedCourses.map((course) => (
            <Card key={course.id} className="mb-2">
              <CardContent className="p-3 flex items-baseline justify-between gap-2">
                <Link href={`/courses/${course.id}`} className="hover:underline">
                  {course.title}
                </Link>
                {course.owner_name && (
                  <span className="text-xs text-muted-foreground">
                    by {course.owner_name}
                  </span>
                )}
              </CardContent>
            </Card>
          ))}
        </>
      )}
    </section>
  );
}
