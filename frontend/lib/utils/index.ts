export const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString();
};

export function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(' ');
}
