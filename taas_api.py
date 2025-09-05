import requests
import pandas as pd
import matplotlib.pyplot as plt
import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import xmltodict
import time
import urllib.parse
import platform
import os
from matplotlib import font_manager, rc

# 폰트 설정
# ⭐️ 추가: OS에 따라 한글 폰트 설정
if platform.system() == 'Darwin': # Mac
    rc('font', family='AppleGothic')
elif platform.system() == 'Windows': # Window
    # C:\Windows\Fonts 경로에서 폰트 파일을 찾습니다.
    # 여러 폰트가 있을 수 있으므로 나눔고딕, 맑은고딕 순으로 시도합니다.
    font_name = font_manager.FontProperties(fname=os.path.join("C:\\Windows\\Fonts", "malgun.ttf")).get_name()
    rc('font', family=font_name)
    # 폰트가 없는 경우
    if font_name is None:
        print("맑은 고딕 폰트를 찾을 수 없습니다. 나눔고딕으로 시도합니다.")
        try:
            font_path = font_manager.findfont(font_manager.FontProperties(family='NanumGothic'))
            font_name = font_manager.FontProperties(fname=font_path).get_name()
            rc('font', family=font_name)
        except Exception:
            print("나눔고딕 폰트도 찾을 수 없습니다. 다른 폰트를 설치하거나 기본 폰트로 실행합니다.")
            pass
else: # Linux or 기타
    # Linux의 경우, 'NanumGothic' 또는 'UnDotum' 같은 폰트가 설치되어 있어야 합니다.
    try:
        font_path = font_manager.findfont(font_manager.FontProperties(family='NanumGothic'))
        font_name = font_manager.FontProperties(fname=font_path).get_name()
        rc('font', family=font_name)
    except Exception:
        print("나눔고딕 폰트를 찾을 수 없습니다. 다른 폰트를 설치하거나 기본 폰트로 실행합니다.")
        pass

# 유니코드 깨짐 방지
plt.rcParams['axes.unicode_minus'] = False

# API 설정
proxies = {}

# API 키를 URL 인코딩되지 않은 상태로 저장
AUTH_KEY = "your api"
BASE_URL = "https://opendata.koroad.or.kr/data/rest/stt"

# 파라미터 목록
YEARS = range(2010, 2025)

# 도시 코드 목록
SIDO_CODES = {
    '서울특별시': '1100', '부산광역시': '1200', '대구광역시': '2200', '인천광역시': '2300',
    '광주광역시': '2400', '대전광역시': '2500', '울산광역시': '2600', '세종특별자치시': '2700',
    '경기도': '1300', '강원특별자치도': '1400', '충청북도': '1500', '충청남도': '1600',
    '전북특별자치도': '1700', '전라남도': '1800', '경상북도': '1900', '경상남도': '2000',
    '제주특별자치도': '2100'
}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("전국 교통사고 위험도 분석기")
        self.geometry("1200x800")
        ctk.set_appearance_mode("System")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        self.is_loading = False
        self.stop_loading = False
        self.current_sido_code = None
        self.current_year_index = 0
        self.current_gugun_index = 1
        
        self.df = pd.DataFrame()
        self.all_data = []

        self.create_input_frame()

    def create_input_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        input_frame = ctk.CTkFrame(self.main_frame)
        input_frame.pack(expand=True, padx=20, pady=20)

        ctk.CTkLabel(input_frame, text="전국 교통사고 데이터 분석기", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(20, 10))
        ctk.CTkLabel(input_frame, text="원하는 지역을 선택하여 데이터를 불러오세요.").pack(pady=(0, 20))

        # 지역별 버튼 생성
        button_frame = ctk.CTkFrame(input_frame)
        button_frame.pack(pady=20)
        button_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        row, col = 0, 0
        for city, code in SIDO_CODES.items():
            button = ctk.CTkButton(button_frame, text=city, command=lambda c=code: self.start_data_load_thread(sido_code=c))
            button.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            col += 1
            if col > 3:
                col = 0
                row += 1

        # 루프 제어 및 통계 분석 버튼
        control_frame = ctk.CTkFrame(input_frame)
        control_frame.pack(pady=10)
        
        self.stop_button = ctk.CTkButton(control_frame, text="중지", command=self.stop_data_load, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        
        self.resume_button = ctk.CTkButton(control_frame, text="재개", command=self.resume_data_load, state="disabled")
        self.resume_button.pack(side="left", padx=5)
        
        self.analyze_button = ctk.CTkButton(control_frame, text="통계 분석", command=self.start_analysis_thread, state="disabled")
        self.analyze_button.pack(side="left", padx=5)
        
        self.loading_label = ctk.CTkLabel(input_frame, text="")
        self.loading_label.pack(pady=10)
        
        self.log_textbox = ctk.CTkTextbox(input_frame, width=500, height=200, corner_radius=10)
        self.log_textbox.pack(pady=20)
        self.log_textbox.insert("end", "로그가 여기에 출력됩니다...\n")
        self.log_textbox.configure(state="disabled")

    def update_log(self, message):
        """로그 메시지를 텍스트 상자에 추가하는 헬퍼 함수"""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def start_data_load_thread(self, sido_code):
        # 새로운 로딩 시작 시 초기화
        self.is_loading = True
        self.stop_loading = False
        self.current_sido_code = sido_code
        self.current_year_index = 0
        self.current_gugun_index = 1
        self.all_data = []
        self.df = pd.DataFrame()
        
        self.loading_label.configure(text=f"{[k for k,v in SIDO_CODES.items() if v==sido_code][0]} 데이터를 불러오는 중입니다...")
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.resume_button.configure(state="disabled")
        self.analyze_button.configure(state="disabled")
        self.update_idletasks()
        
        load_thread = threading.Thread(target=self.load_data)
        load_thread.start()
        
    def stop_data_load(self):
        self.stop_loading = True
        self.loading_label.configure(text="데이터 수집 중지됨.")
        self.stop_button.configure(state="disabled")
        self.resume_button.configure(state="normal")
        self.analyze_button.configure(state="normal")
        
    def resume_data_load(self):
        self.stop_loading = False
        self.loading_label.configure(text="데이터 수집 재개...")
        self.stop_button.configure(state="normal")
        self.resume_button.configure(state="disabled")
        self.analyze_button.configure(state="disabled")
        
        load_thread = threading.Thread(target=self.load_data)
        load_thread.start()

    def load_data(self):
        try:
            self.after(0, lambda: self.update_log("데이터 로딩을 시작합니다. 잠시만 기다려 주세요..."))
            
            encoded_auth_key = urllib.parse.quote(AUTH_KEY, safe='')
            
            for year in YEARS[self.current_year_index:]:
                self.current_year_index = YEARS.index(year)
                
                for i in range(self.current_gugun_index, 100):
                    if self.stop_loading:
                        self.is_loading = False
                        self.after(0, lambda: self.update_log("------------------------------------------"))
                        self.after(0, lambda: self.update_log("데이터 수집이 사용자에 의해 중지되었습니다."))
                        self.after(0, self.stop_button.configure(state="disabled"))
                        self.after(0, self.resume_button.configure(state="normal"))
                        self.after(0, self.analyze_button.configure(state="normal"))
                        return
                    
                    self.current_gugun_index = i
                    gugun_code_suffix = str(i).zfill(2)
                    gugun_code = self.current_sido_code[:2] + gugun_code_suffix
                    
                    try:
                        request_url = f"{BASE_URL}?authKey={encoded_auth_key}&searchYearCd={year}&sido={self.current_sido_code}&gugun={gugun_code}"
                        self.after(0, lambda url=request_url: self.update_log(f"-> 요청 URL: {url}"))
                        
                        response = requests.get(request_url, timeout=5, proxies=proxies)
                        response.raise_for_status()
                        
                        xml_data = response.content.decode('utf-8')
                        
                        data_dict = xmltodict.parse(xml_data)
                        result_msg = data_dict.get('response', {}).get('header', {}).get('resultMsg', None)

                        # NODATA_ERROR 발생 시 즉시 루프 중지
                        if result_msg == 'NODATA_ERROR':
                            self.after(0, lambda g=gugun_code: self.update_log(f"   ❌ NODATA_ERROR for {g}. 해당 지역 데이터 없음. 루프를 중지합니다."))
                            self.stop_data_load()
                            return
                        else:
                            self.after(0, lambda: self.update_log(f"   ✅ XML 수령 완료!"))
                            self.after(0, lambda: self.update_log(xml_data))
                            
                            items = data_dict.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                            
                            if isinstance(items, list):
                                self.all_data.extend(items)
                            elif items:
                                self.all_data.append(items)

                        time.sleep(0.1)
                            
                    except requests.exceptions.HTTPError as e:
                        self.after(0, lambda s=e.response.status_code, g=gugun_code: self.update_log(f"   ⚠️ 치명적 HTTP 오류: {s} for {g}. 스킵합니다."))
                        time.sleep(0.5)
                        continue
                    except Exception as e:
                        self.after(0, lambda err=e: self.update_log(f"   🚨 예상치 못한 오류 발생: {err}. 스킵합니다."))
                        time.sleep(0.5)
                        continue
                self.current_gugun_index = 1

            self.is_loading = False
            self.after(0, lambda: self.loading_label.configure(text="데이터 수집 완료!"))
            self.after(0, lambda: self.update_log("------------------------------------------"))
            self.after(0, lambda: self.update_log("모든 데이터 수집이 완료되었습니다. 통계 분석을 시작하세요."))
            self.after(0, self.stop_button.configure(state="disabled"))
            self.after(0, self.resume_button.configure(state="disabled"))
            self.after(0, self.analyze_button.configure(state="normal"))

        except Exception as e:
            self.is_loading = False
            self.after(0, lambda: self.loading_label.configure(text="데이터 로딩 중 최종 오류 발생!"))
            self.after(0, lambda: self.update_log(f"최종 오류 발생: {e}. 프로그램을 다시 시작해 보세요."))
            self.after(0, self.stop_button.configure(state="disabled"))
            self.after(0, self.resume_button.configure(state="disabled"))
            self.after(0, self.analyze_button.configure(state="normal"))

    def start_analysis_thread(self):
        if not self.all_data:
            self.after(0, lambda: self.loading_label.configure(text="분석할 데이터가 없습니다. 먼저 데이터를 수집하세요."))
            return
            
        self.loading_label.configure(text="통계 분석 및 대시보드 생성 중...")
        analysis_thread = threading.Thread(target=self.run_analysis)
        analysis_thread.start()

    def run_analysis(self):
        try:
            self.df = pd.DataFrame(self.all_data)
            self.after(0, lambda: self.update_log("데이터프레임 생성 완료. 대시보드를 생성합니다."))
            self.after(0, self.show_dashboard)
        except Exception as e:
            self.after(0, lambda: self.loading_label.configure(text="통계 분석 중 오류 발생!"))
            self.after(0, lambda: self.update_log(f"분석 오류: {e}"))

    def show_dashboard(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        dashboard_frame = ctk.CTkScrollableFrame(self.main_frame)
        dashboard_frame.pack(expand=True, fill="both")
        dashboard_frame.grid_columnconfigure((0, 1), weight=1)
        
        ctk.CTkLabel(dashboard_frame, text="교통사고 위험도 대시보드", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, columnspan=2, pady=20, sticky="ew")

        self.analyze_and_create_charts(dashboard_frame)
        
    def analyze_and_create_charts(self, frame):
        full_accident_df = self.df[self.df['acc_cl_nm'] == '전체사고'].copy()
        if full_accident_df.empty:
            ctk.CTkLabel(frame, text="전체사고 데이터가 없습니다.", font=ctk.CTkFont(size=16)).grid(row=1, column=0, columnspan=2, padx=10, pady=10)
            return

        numeric_cols = ['dth_dnv_cnt', 'ftlt_rate', 'cnt_027_01', 'cnt_027_02', 'cnt_027_03', 'cnt_027_04', 'cnt_027_05', 'cnt_027_06', 'cnt_027_07', 'cnt_014_01', 'cnt_014_02', 'cnt_014_03', 'cnt_014_04']
        for col in numeric_cols:
            full_accident_df[col] = pd.to_numeric(full_accident_df[col], errors='coerce').fillna(0)
        
        full_accident_df['road_fatality'] = full_accident_df['ftlt_rate']
        top_10_road_fatality = full_accident_df.sort_values('road_fatality', ascending=False).head(10)
        self.create_chart(frame, top_10_road_fatality, 'road_fatality', "도로 치명도 (%)", "도로 치명도 TOP 10 지역", 1, 0, 'purple')

        top_10_dth_dnv = full_accident_df.sort_values('dth_dnv_cnt', ascending=False).head(10)
        self.create_chart(frame, top_10_dth_dnv, 'dth_dnv_cnt', "사망자수 (명)", "사망자수 TOP 10 지역", 1, 1, 'skyblue')
        
        violation_cols = ['cnt_027_01', 'cnt_027_02', 'cnt_027_03', 'cnt_027_04', 'cnt_027_05', 'cnt_027_06', 'cnt_027_07']
        violation_names = ['과속', '중앙선 침범', '신호위반', '안전거리 미확보', '안전운전 의무 불이행', '보행자 보호 의무 위반', '기타']
        
        violation_data = [full_accident_df[col].sum() for col in violation_cols]
        violation_data = pd.Series(violation_data, index=violation_names)

        self.create_pie_chart(frame, violation_data, "전국 법규위반 사고 원인 비율", 2, 0)
        
        type_cols = ['cnt_014_01', 'cnt_014_02', 'cnt_014_03', 'cnt_014_04']
        type_names = ['차대사람', '차대차', '차량단독', '철길건널목']
        
        type_data = [full_accident_df[col].sum() for col in type_cols]
        type_data = pd.Series(type_data, index=type_names)

        self.create_pie_chart(frame, type_data, "전국 사고 유형별 건수 비율", 2, 1)

    def create_chart(self, frame, data, value_col, x_label, title, row, col, color):
        if data.empty:
            ctk.CTkLabel(frame, text="데이터 없음", font=ctk.CTkFont(size=14)).grid(row=row, column=col, padx=10, pady=10)
            return

        chart_frame = ctk.CTkFrame(frame, corner_radius=10)
        chart_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(chart_frame, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        fig, ax = plt.subplots(figsize=(6, 4), facecolor='#f0f0f0')
        ax.barh(data['sido_sgg_nm'], data[value_col], color=color, height=0.6)
        ax.set_xlabel(x_label, fontsize=10)
        ax.tick_params(axis='y', labelsize=9)
        ax.grid(axis='x', linestyle='--', alpha=0.7)
        fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(expand=True, fill="both")
    
    def create_pie_chart(self, frame, data, title, row, col):
        if data.empty or data.sum() == 0:
            ctk.CTkLabel(frame, text="데이터 없음", font=ctk.CTkFont(size=14)).grid(row=row, column=col, padx=10, pady=10)
            return
            
        chart_frame = ctk.CTkFrame(frame, corner_radius=10)
        chart_frame.grid(row=row, column=col, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(chart_frame, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        fig, ax = plt.subplots(figsize=(6, 6), facecolor='#f0f0f0')
        ax.pie(data, labels=data.index, autopct='%1.1f%%', startangle=90, colors=plt.cm.Pastel1.colors)
        ax.axis('equal')
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(expand=True, fill="both")

if __name__ == "__main__":
    app = App()
    app.mainloop()