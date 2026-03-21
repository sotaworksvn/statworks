"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useAppStore } from "@/lib/store";
import { uploadFile } from "@/lib/api";
import { toast } from "sonner";
import * as XLSX from "xlsx";

const MAX_FILES = 3;

// Only Excel + CSV — no docx/pptx context files from frontend dropzone
const ACCEPTED_TYPES: Record<string, string[]> = {
  "application/vnd.ms-excel": [".xls"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "text/csv": [".csv"],
  "application/csv": [".csv"],
};

/**
 * Parse an Excel or CSV file locally using SheetJS.
 * Returns { columns, rows } for immediate rendering in Data Viewer.
 */
function parseLocally(
  file: File,
  buffer: ArrayBuffer,
): { columns: string[]; rows: Record<string, unknown>[] } | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (ext !== ".xlsx" && ext !== ".xls" && ext !== ".csv") return null;

  try {
    const workbook = XLSX.read(buffer, { type: "array" });
    const sheetName = workbook.SheetNames[0];
    if (!sheetName) return null;
    const sheet = workbook.Sheets[sheetName];
    const jsonData = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, {
      defval: "",
    });
    const columns = jsonData.length > 0 ? Object.keys(jsonData[0]) : [];
    return { columns, rows: jsonData };
  } catch {
    return null;
  }
}

export function UploadZone() {
  const { setUploadState, setIsUploading, addUploadedFile, setLocalParsedData, user } =
    useAppStore();

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      setIsUploading(true);

      // Parse locally with SheetJS for instant Data Viewer rendering
      const primaryFile = acceptedFiles[0];
      const buffer = await primaryFile.arrayBuffer();
      const localData = parseLocally(primaryFile, buffer);

      try {
        const result = await uploadFile(acceptedFiles, user?.id);

        setUploadState({
          fileId: result.file_id,
          datasetName: primaryFile.name,
          rowCount: result.row_count,
          columns: [...result.columns],
        });

        // Register file in uploadedFiles for Data Viewer tabs AND upload history
        const ext = primaryFile.name.slice(primaryFile.name.lastIndexOf(".")).toLowerCase();
        addUploadedFile({
          id: result.file_id,
          name: primaryFile.name,
          type: ext,
          content_hash: null,
          uploaded_at: new Date().toISOString(),
          columns: [...result.columns],
          row_count: result.row_count,
          file_size: primaryFile.size,
        });

        // Store locally-parsed data for instant Data Viewer rendering
        if (localData) {
          setLocalParsedData(result.file_id, localData);
        }

        toast.success(`Đã upload "${primaryFile.name}" thành công!`);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload thất bại";
        toast.error(message);
      } finally {
        setIsUploading(false);
      }
    },
    [setUploadState, setIsUploading, addUploadedFile, setLocalParsedData, user],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxFiles: MAX_FILES,
    maxSize: 20 * 1024 * 1024, // 20 MB
    onDropRejected: (rejections) => {
      const firstError = rejections[0]?.errors[0];
      if (firstError?.code === "file-too-large") {
        toast.error("File vượt quá giới hạn 20 MB.");
      } else if (firstError?.code === "file-invalid-type") {
        toast.error("Định dạng không hỗ trợ. Chỉ chấp nhận .xlsx, .xls, .csv");
      } else if (firstError?.code === "too-many-files") {
        toast.error(`Tối đa ${MAX_FILES} file mỗi lần upload.`);
      } else {
        toast.error(firstError?.message ?? "File bị từ chối");
      }
    },
  });

  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div
        {...getRootProps()}
        id="upload-zone"
        className={`flex w-full max-w-xl flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all ${
          isDragActive
            ? "border-[#FF6B4A] bg-[#FF6B4A]/5"
            : "border-gray-200 bg-[#F5F5F7]/50 hover:border-[#2D3561]/30 hover:bg-[#F5F5F7]"
        }`}
      >
        <input {...getInputProps()} />

        <div className="text-5xl">{isDragActive ? "📥" : "📊"}</div>

        <div>
          <p className="font-semibold text-[#2D3561] text-lg mb-1">
            {isDragActive ? "Thả file vào đây..." : "Kéo thả file bảng điểm vào đây"}
          </p>
          <p className="text-gray-400 text-sm">
            hoặc click để chọn · Tối đa {MAX_FILES} file · 20 MB mỗi file
          </p>
        </div>

        {/* Format badges */}
        <div className="flex gap-2">
          {[".xlsx", ".xls", ".csv"].map((fmt) => (
            <span
              key={fmt}
              className="px-2.5 py-1 rounded-lg bg-gray-100 text-xs font-medium text-gray-600 border border-gray-200"
            >
              {fmt}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
