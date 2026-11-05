export const DISCIPLINES = ["architecture", "structure", "fire", "plumbing", "hvac", "electrical", "elv", "other"] as const;
export type Discipline = (typeof DISCIPLINES)[number];
export type Staged = { file: File; path: string; discipline: Discipline };

const WORD = (codes: string) => `(?:^|[^a-z])(?:${codes})(?:[^a-z]|$)`;
// Offices mark the discipline with a code in the file or folder name, or say it in Georgian.
const RULES: [Discipline, RegExp][] = [
  ["fire", new RegExp(`${WORD("ff|fas|fps|fire")}|ხანძარ|სახანძრო|sprink`, "i")],
  ["elv", new RegExp(`${WORD("elv|low.?voltage")}|სუსტი დენ`, "i")],
  ["electrical", new RegExp(`${WORD("el|elec")}|ელექტრო|electric`, "i")],
  ["hvac", new RegExp(`${WORD("hc|hvac|vn|vent")}|გათბობ|გაგრილებ|ვენტილაც|სავენტილაციო|კონდიცირ`, "i")],
  ["plumbing", new RegExp(`${WORD("pl|sw|dr")}|წყალ|კანალიზაც|plumb|sewage`, "i")],
  ["structure", new RegExp(`${WORD("st|str|kr")}|კონსტრუქც|struct`, "i")],
  ["architecture", new RegExp(`${WORD("ar|arc|arch")}|არქიტექტ|archit`, "i")],
];

export function guessDiscipline(path: string): Discipline {
  return RULES.find(([, pattern]) => pattern.test(path))?.[0] ?? "other";
}

export const isDrawing = (name: string) => /\.(pdf|dwg|dxf)$/i.test(name);
export const isCad = (name: string) => /\.(dwg|dxf)$/i.test(name);

/** Discipline order, then floors in number order. */
export function ordered(staged: Staged[]) {
  return [...staged].sort(
    (a, b) =>
      DISCIPLINES.indexOf(a.discipline) - DISCIPLINES.indexOf(b.discipline) ||
      a.file.name.localeCompare(b.file.name, undefined, { numeric: true }),
  );
}

/** The folder they came from, or else the first file's name. */
export function projectName(staged: Staged[]) {
  const top = new Set(staged.map((s) => (s.path.includes("/") ? s.path.split("/")[0] : "")));
  const [folder] = top;
  if (top.size === 1 && folder && !/^(dwg|dxf|pdf|cad)$/i.test(folder)) return folder;
  const first = staged[0]?.file.name.replace(/\.[^.]+$/, "") ?? "";
  return staged.length > 1 ? `${first} +${staged.length - 1}` : first;
}

function entryFiles(entry: FileSystemEntry, path: string): Promise<{ file: File; path: string }[]> {
  if (entry.isFile) {
    return new Promise((resolve) =>
      (entry as FileSystemFileEntry).file(
        (file) => resolve([{ file, path: `${path}${file.name}` }]),
        () => resolve([]),
      ),
    );
  }
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  return new Promise((resolve) => {
    const all: FileSystemEntry[] = [];
    // A directory reader gives its entries in batches, and an empty batch means the end.
    const next = () =>
      reader.readEntries(async (batch) => {
        if (batch.length) {
          all.push(...batch);
          next();
          return;
        }
        const nested = await Promise.all(all.map((item) => entryFiles(item, `${path}${entry.name}/`)));
        resolve(nested.flat());
      }, () => resolve([]));
    next();
  });
}

/** Everything dropped, including what is inside dropped folders. */
export async function droppedFiles(data: DataTransfer) {
  const entries = [...data.items].map((item) => item.webkitGetAsEntry()).filter((e): e is FileSystemEntry => Boolean(e));
  if (!entries.length) return [...data.files].map((file) => ({ file, path: file.name }));
  return (await Promise.all(entries.map((entry) => entryFiles(entry, "")))).flat();
}
