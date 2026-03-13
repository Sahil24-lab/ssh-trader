/* 8.4 components/LoadingSpinner.tsx */
export default function LoadingSpinner() {
  return (
    <div className="flex justify-center items-center py-10">
      <div className="w-12 h-12 border-4 border-teal-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
