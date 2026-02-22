import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import math
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- 起動時メッセージ ---
print("====================================================")
print("     レーザー加工パス生成ツール  Ver 3.8")
print("====================================================")
print(" [1/3] システムを起動しています...")
print(" [2/3] ライブラリを読み込み中 (Pandas/Matplotlib)...")
print(" [3/3] 画面を表示します。しばらくお待ちください。")
print("----------------------------------------------------")
print(" ※この黒い画面を閉じるとソフトも終了します。")
print(" ※エラー時はここに詳細が表示されます。")
print("====================================================")

def generate_laser_path(input_file, start_y_mode, start_x_mode, hole_skip, v_blocks, h_blocks):
    df_orig = pd.read_csv(input_file, names=["x", "y"], header=None)
    df_orig["x"] = pd.to_numeric(df_orig["x"].astype(str).str.replace("\xa0","",regex=False).str.strip(), errors="coerce")
    df_orig["y"] = pd.to_numeric(df_orig["y"].astype(str).str.replace("\xa0","",regex=False).str.strip(), errors="coerce")
    df_orig = df_orig.dropna()

    unique_y = np.sort(df_orig['y'].unique())
    if start_y_mode == "上から": unique_y = unique_y[::-1]
    
    num_rows = len(unique_y)
    rows_per_block = math.ceil(num_rows / v_blocks)
    x_min, x_max = df_orig["x"].min(), df_orig["x"].max()
    x_width = (x_max - x_min) / h_blocks if x_max != x_min else 1

    sorted_path = []
    for h_off in range(hole_skip):
        for r_inner in range(rows_per_block):
            for vb in range(v_blocks):
                row_idx = r_inner + (vb * rows_per_block)
                if row_idx >= num_rows: continue
                target_y = unique_y[row_idx]
                row_data = df_orig[df_orig['y'] == target_y]
                for hb in range(h_blocks):
                    bx_start = x_min + hb * x_width
                    bx_end = bx_start + x_width
                    if hb == h_blocks - 1:
                        block_holes = row_data[(row_data['x'] >= bx_start) & (row_data['x'] <= x_max + 0.001)]
                    else:
                        block_holes = row_data[(row_data['x'] >= bx_start) & (row_data['x'] < bx_end)]
                    if block_holes.empty: continue
                    is_asc = (start_x_mode == "左から")
                    block_holes_sorted = block_holes.sort_values(by='x', ascending=is_asc).values.tolist()
                    picked = [block_holes_sorted[j] for j in range(h_off, len(block_holes_sorted), hole_skip)]
                    sorted_path.extend(picked)

    processed_set = set(tuple(h) for h in sorted_path)
    all_data = df_orig.values.tolist()
    for h in all_data:
        if tuple(h) not in processed_set: sorted_path.append(h)
    return df_orig, pd.DataFrame(sorted_path, columns=['x', 'y'])

def show_animation(df_orig, display_df, original_file_path, title="Preview", show_save=True):
    ani_window = tk.Toplevel(root)
    ani_window.title(f"{title}")
    ani_window.geometry("700x850")

    fig = Figure(figsize=(5, 5), dpi=100)
    ax = fig.add_subplot(111); ax.set_aspect("equal")
    ax.set_xlim(df_orig["x"].min() - 2, df_orig["x"].max() + 2)
    ax.set_ylim(df_orig["y"].min() - 2, df_orig["y"].max() + 2)
    ax.set_title(title)

    ax.scatter(df_orig["x"], df_orig["y"], color="lightgrey", s=2, alpha=0.3)
    processed_scat = ax.scatter([], [], color="blue", s=5)
    current_head = ax.scatter([], [], color="red", s=30, edgecolor="black", zorder=5)

    step = 20
    total_len = len(display_df)
    num_frames = (total_len // step) + 1
    state = {"running": True, "frame_idx": 0}

    def update_plot(f_idx):
        state["frame_idx"] = f_idx
        end_idx = min((f_idx + 1) * step, total_len)
        current_data = display_df.iloc[:end_idx]
        processed_scat.set_offsets(current_data[["x", "y"]])
        if end_idx > 0:
            last_hole = display_df.iloc[end_idx - 1]
            current_head.set_offsets([[last_hole["x"], last_hole["y"]]])
        else:
            current_head.set_offsets(np.empty((0, 2)))
        canvas.draw_idle()

    canvas = FigureCanvasTkAgg(fig, master=ani_window)
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    ctrl = tk.Frame(ani_window); ctrl.pack(pady=10)
    ani = FuncAnimation(fig, lambda f: update_plot(f) if state["running"] else None, frames=num_frames, interval=50, repeat=True)

    def toggle():
        if state["running"]:
            ani.pause(); btn_p.config(text="▶ 再生", bg="lightgreen"); state["running"] = False
        else:
            ani.resume(); btn_p.config(text="|| 停止", bg="orange"); state["running"] = True

    tk.Button(ctrl, text="|< 最初へ", command=lambda: [ani.frame_seq == ani.new_frame_seq(), update_plot(0)]).pack(side=tk.LEFT, padx=2)
    tk.Button(ctrl, text="< 戻す", command=lambda: update_plot(max(0, state["frame_idx"]-1)) if not state["running"] else None).pack(side=tk.LEFT, padx=2)
    btn_p = tk.Button(ctrl, text="|| 停止", command=toggle, width=10, bg="orange", font=("", 9, "bold"))
    btn_p.pack(side=tk.LEFT, padx=5)
    tk.Button(ctrl, text="送る >", command=lambda: update_plot(min(num_frames-1, state["frame_idx"]+1)) if not state["running"] else None).pack(side=tk.LEFT, padx=2)
    tk.Button(ctrl, text="最後へ >|", command=lambda: [ani.pause(), btn_p.config(text="▶ 再生"), state.update({"running": False}), update_plot(num_frames-1)]).pack(side=tk.LEFT, padx=2)

    if show_save:
        btn_save = tk.Button(ani_window, text="このパスで名前を付けて保存", command=lambda: save_file(display_df, original_file_path), 
                             bg="#2196F3", fg="white", font=("", 12, "bold"), height=2)
        btn_save.pack(fill=tk.X, padx=50, pady=20)
    ani_window.ani = ani
    canvas.draw()

def save_file(sorted_df, original_file_path):
    f_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                          initialfile=os.path.basename(original_file_path).replace(".csv", "_sorted.csv"))
    if f_path:
        sorted_df.to_csv(f_path, index=False, header=False)
        messagebox.showinfo("完了", "保存しました")

def run_sorted_preview():
    try:
        print(f"INFO: 最適化計算を開始しました...")
        df_orig, sorted_df = generate_laser_path(file_ent.get(), y_var.get(), x_var.get(), int(skip_ent.get()), int(v_ent.get()), int(h_ent.get()))
        show_animation(df_orig, sorted_df, file_ent.get(), title="Optimized Path", show_save=True)
    except Exception as e: messagebox.showerror("エラー", str(e))

def run_original_preview():
    try:
        file_path = file_ent.get()
        if not os.path.exists(file_path): raise ValueError("ファイルを選択してください")
        df_orig = pd.read_csv(file_path, names=["x", "y"], header=None)
        df_orig["x"] = pd.to_numeric(df_orig["x"].astype(str).str.replace("\xa0","",regex=False).str.strip(), errors="coerce")
        df_orig["y"] = pd.to_numeric(df_orig["y"].astype(str).str.replace("\xa0","",regex=False).str.strip(), errors="coerce")
        df_orig = df_orig.dropna()
        show_animation(df_orig, df_orig, file_path, title="Original Path", show_save=False)
    except Exception as e: messagebox.showerror("エラー", str(e))

root = tk.Tk(); root.title("レーザーパス生成ツール Ver 3.8"); root.geometry("500x600")
f_lab = tk.LabelFrame(root, text=" 1. ファイル選択 ", padx=10, pady=10, font=("", 9, "bold"))
f_lab.pack(padx=20, pady=10, fill="x")
file_ent = tk.Entry(f_lab, width=40); file_ent.pack(side=tk.LEFT, padx=5)
tk.Button(f_lab, text="参照", command=lambda: [file_ent.delete(0,tk.END), file_ent.insert(0,filedialog.askopenfilename())]).pack(side=tk.LEFT)
mid_frame = tk.Frame(root); mid_frame.pack(padx=20, pady=5, fill="x")
pos_lab = tk.LabelFrame(mid_frame, text=" 2. 開始位置 ", padx=10, pady=10, font=("", 9, "bold"))
pos_lab.pack(side=tk.LEFT, fill="both", expand=True, padx=(0,5))
y_var = tk.StringVar(value="下から"); tk.OptionMenu(pos_lab, y_var, "下から", "上から").pack(fill="x")
x_var = tk.StringVar(value="左から"); tk.OptionMenu(pos_lab, x_var, "左から", "右から").pack(fill="x")
set_lab = tk.LabelFrame(mid_frame, text=" 3. 分割・飛ばし設定 ", padx=10, pady=10, font=("", 9, "bold"))
set_lab.pack(side=tk.LEFT, fill="both", expand=True, padx=(5,0))
tk.Label(set_lab, text="縦ブロック:").grid(row=0, column=0, sticky="e")
v_ent = tk.Entry(set_lab, width=5); v_ent.insert(0, "2"); v_ent.grid(row=0, column=1, sticky="w")
tk.Label(set_lab, text="横ブロック:").grid(row=1, column=0, sticky="e")
h_ent = tk.Entry(set_lab, width=5); h_ent.insert(0, "1"); h_ent.grid(row=1, column=1, sticky="w")
tk.Label(set_lab, text="穴スキップ:").grid(row=2, column=0, sticky="e")
skip_ent = tk.Entry(set_lab, width=5); skip_ent.insert(0, "5"); skip_ent.grid(row=2, column=1, sticky="w")
act_lab = tk.LabelFrame(root, text=" 4. 実行 ", padx=10, pady=10, font=("", 9, "bold"))
act_lab.pack(padx=20, pady=10, fill="x")
tk.Button(act_lab, text="元の順序を確認", command=run_original_preview, bg="#f0f0f0", height=2).pack(fill="x", pady=2)
tk.Button(act_lab, text="最適化プレビュー表示", command=run_sorted_preview, bg="#4CAF50", fg="white", font=("", 11, "bold"), height=2).pack(fill="x", pady=5)
root.mainloop()