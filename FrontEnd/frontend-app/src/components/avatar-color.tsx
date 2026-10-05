const COLORS = [
  "bg-red-500 dark:bg-red-400",
  "bg-pink-500 dark:bg-pink-400",
  "bg-purple-500 dark:bg-purple-400",
  "bg-indigo-500 dark:bg-indigo-400",
  "bg-blue-500 dark:bg-blue-400",
  "bg-cyan-500 dark:bg-cyan-400",
  "bg-teal-500 dark:bg-teal-400",
  "bg-green-500 dark:bg-green-400",
  "bg-yellow-500 dark:bg-yellow-400",
  "bg-orange-500 dark:bg-orange-400",
];

export const getAvatarColor = (name: string): string => {
  if (!name) return "bg-gray-300 dark:bg-gray-600";

  let hash = 5381;

  for (let i = 0; i < name.length; i++) {
    hash = (hash * 33) ^ name.charCodeAt(i);
  }

  return COLORS[Math.abs(hash) % COLORS.length];
};