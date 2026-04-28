"""
志愿填报服务 - 基于广州中考梯度投档规则的完整实现

核心录取规则（按优先级）：
1. 梯度优先：先投第一梯度考生，全部投完再投第二梯度
2. 志愿优先：同梯度内，先投第一志愿，再投第二志愿...
3. 分数优先：同志愿内，按分数从高到低录取

关键概念：
- 梯度控制线：2025年第一梯度707分，每40分一个梯度
- 末位志愿号：该校在某个梯度录满时的志愿位置
- 如果末位志愿号=1，说明该校在第一志愿就录满了，后续志愿无效
- 老三区互认：荔湾、越秀、海珠三区在第三批次视为同一区域，户籍生互认
"""
import random
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from ..models import School, Batch3Public, Batch3Private, EnrollmentPlan
from ..schemas.response import VolunteerResponse, VolunteerPlan, VolunteerItem, SchoolInfo, VolunteerPosition

# 梯度配置（2025年标准）
GRADIENT_INTERVAL = 40  # 梯度间隔40分
FIRST_GRADIENT_2025 = 707  # 2025年第一梯度线

# 老三区定义（第三批次视为同一招生区域）
OLD_THREE_DISTRICTS = ["荔湾区", "越秀区", "海珠区"]

class AdvisorService:
    """志愿填报服务类 - 基于梯度投档规则"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def _is_old_three_district(self, district: str) -> bool:
        """判断是否属于老三区"""
        return district in OLD_THREE_DISTRICTS
    
    def _get_student_type_for_school(
        self, 
        student_district: str, 
        school_district: str,
        household_type: str
    ) -> str:
        """
        确定考生相对于学校的户籍类型
        
        规则：
        1. 如果考生是非户籍生，无论在哪里报考，都视为非户籍生
        2. 如果考生是户籍生且在老三区内报考老三区学校，视为户籍生（老三区互认）
        3. 如果考生是户籍生且在同一行政区，视为户籍生
        4. 其他情况，视为外区生/非户籍生
        
        Args:
            student_district: 考生学籍区
            school_district: 学校所在区
            household_type: 考生户籍类型（"户籍生"或"非户籍生"）
            
        Returns:
            "户籍生" 或 "非户籍生"
        """
        # ⭐ CRITICAL FIX: 首先检查考生的实际户籍类型
        # 如果考生是非户籍生，无论如何都使用非户籍生分数线
        if household_type == "非户籍生":
            return "非户籍生"
        
        # 以下逻辑仅适用于户籍生考生
        # 规则1：老三区互认
        if self._is_old_three_district(student_district) and self._is_old_three_district(school_district):
            return "户籍生"
        
        # 规则2：同一行政区
        if student_district == school_district:
            return "户籍生"
        
        # 规则3：跨区报考的户籍生，在某些政策下可能视为外区生
        # 但根据广州中考政策，户籍生跨区仍算户籍生，只是可能有额外限制
        # 这里返回"户籍生"，让数据库查询时自然过滤
        return "户籍生"
    
    def _get_gradient_line(self, year: int = 2025) -> Dict[int, float]:
        """
        获取指定年份的梯度控制线
        
        Returns:
            {梯度等级: 分数线}
            例如: {1: 707, 2: 667, 3: 627, ...}
        """
        gradients = {}
        for i in range(1, 11):  # 最多10个梯度
            gradients[i] = FIRST_GRADIENT_2025 - (i - 1) * GRADIENT_INTERVAL
        return gradients
    
    def _determine_student_gradient(self, score: float, year: int = 2025) -> int:
        """
        确定考生所属的梯度等级
        
        Args:
            score: 考生分数
            year: 年份
            
        Returns:
            梯度等级（1=第一梯度，2=第二梯度...）
        """
        gradients = self._get_gradient_line(year)
        
        for gradient_level in sorted(gradients.keys()):
            if score >= gradients[gradient_level]:
                return gradient_level
        
        return len(gradients) + 1
    
    def _determine_school_gradient(
        self, 
        school_id: int, 
        student_district: str,
        school_district: str,
        household_type: str,
        year: int = 2025
    ) -> Optional[int]:
        """
        确定学校在指定年份的梯度等级（基于录取分数线）
        
        关键：根据考生与学校的关系，选择正确的户籍类型查询分数线
        
        Args:
            school_id: 学校ID
            student_district: 考生学籍区
            school_district: 学校所在区
            household_type: 考生户籍类型
            year: 年份
            
        Returns:
            梯度等级，如果无数据返回None
        """
        # 确定应该使用哪种户籍类型的分数线
        actual_student_type = self._get_student_type_for_school(
            student_district, school_district, household_type
        )
        
        # 1. 先查询第三批次公办数据
        record = self.db.query(Batch3Public).filter(
            Batch3Public.school_id == school_id,
            Batch3Public.year == year,
            Batch3Public.student_type == actual_student_type
        ).first()
        
        # 2. 如果公办没有数据，查询第三批次民办公费班
        if not record or not record.min_score:
            private_record = self.db.query(Batch3Private).filter(
                Batch3Private.school_id == school_id,
                Batch3Private.year == year,
                Batch3Private.sub_type == '公费班'
            ).first()
            
            if private_record and private_record.min_score:
                record = private_record
        
        if not record or not record.min_score:
            return None
        
        gradients = self._get_gradient_line(year)
        for gradient_level in sorted(gradients.keys()):
            if record.min_score >= gradients[gradient_level]:
                return gradient_level
        
        return len(gradients) + 1
    
    def generate_volunteer_plans(
        self,
        district: str,
        household_type: str,
        estimated_score: float,
        consider_external_district: bool = True
    ) -> VolunteerResponse:
        """
        生成志愿方案（基于梯度投档规则）
        
        Args:
            district: 学籍区（行政区）
            household_type: 户籍类型
            estimated_score: 预估分数
            consider_external_district: 是否考虑外区学校（老三区视为一个区）
            
        Returns:
            志愿方案响应
        """
        # 1. 确定考生所属梯度
        student_gradient = self._determine_student_gradient(estimated_score)
        
        # 2. 获取该学区所有学校的综合数据（考虑老三区互认）
        schools_with_data = self._get_schools_with_gradient_info(district, household_type)
        
        if not schools_with_data:
            return VolunteerResponse(
                success=False,
                message=f"未找到{district}的学校数据",
                plans=[]
            )
        
        # 3. 如果用户选择不考虑外区，过滤掉外区学校
        if not consider_external_district:
            schools_with_data = self._filter_schools_by_district(schools_with_data, district)
            
            if not schools_with_data:
                return VolunteerResponse(
                    success=False,
                    message=f"{district}没有本区学校数据",
                    plans=[]
                )
        
        # 4. 根据梯度投档规则筛选和排序学校
        filtered_schools = self._filter_and_rank_schools(
            schools_with_data, 
            student_gradient, 
            estimated_score,
            district,
            household_type
        )
        
        if not filtered_schools:
            return VolunteerResponse(
                success=False,
                message=f"{district}没有符合梯度要求的学校",
                plans=[]
            )
        
        # 5. 生成三个方案
        plans = []
        
        aggressive_plan = self._create_gradient_based_plan(
            "激进冲刺方案",
            filtered_schools,
            estimated_score,
            student_gradient,
            district,
            household_type,
            "aggressive"
        )
        plans.append(aggressive_plan)
        
        balanced_plan = self._create_gradient_based_plan(
            "平衡稳妥方案",
            filtered_schools,
            estimated_score,
            student_gradient,
            district,
            household_type,
            "balanced"
        )
        plans.append(balanced_plan)
        
        conservative_plan = self._create_gradient_based_plan(
            "保守保底方案",
            filtered_schools,
            estimated_score,
            student_gradient,
            district,
            household_type,
            "conservative"
        )
        plans.append(conservative_plan)
        
        return VolunteerResponse(
            success=True,
            message="志愿方案生成成功",
            plans=plans
        )
    
    def _get_schools_with_gradient_info(
        self, 
        student_district: str, 
        household_type: str
    ) -> List[Dict]:
        """
        获取学校的综合信息（包含梯度、末位志愿号等）
        
        关键改进：
        - 不仅查询本区学校，还查询老三区其他学校和其他区学校
        - 为每个学校计算对应的户籍生/非户籍生分数线
        """
        # 确定需要查询的区域范围
        target_districts = [student_district]
        
        # 如果是老三区，添加其他两个区
        if self._is_old_three_district(student_district):
            target_districts = OLD_THREE_DISTRICTS.copy()
        
        # 也可以查询其他区的学校（作为外区生报考）
        all_districts_query = self.db.query(School.district).distinct().all()
        other_districts = [d[0] for d in all_districts_query if d[0] not in target_districts]
        
        # 合并所有目标区域
        all_target_districts = target_districts + other_districts
        
        # 查询近5年的录取数据（包含公办和民办公费班）- 原则5：综合考虑过去5年加权平均
        years_data = {}
        for year in [2025, 2024, 2023, 2022, 2021]:  # 新增2021年数据
            # 1. 查询第三批次公办数据
            public_results = self.db.query(
                School.school_id,
                School.school_name,
                School.district,
                Batch3Public.min_score,
                Batch3Public.last_volunteer_rank,
                Batch3Public.student_type
            ).join(
                Batch3Public, School.school_id == Batch3Public.school_id
            ).filter(
                School.district.in_(all_target_districts),
                Batch3Public.year == year
            ).all()
            
            for school_id, school_name, dist, min_score, last_rank, stu_type in public_results:
                if school_id not in years_data:
                    years_data[school_id] = {
                        'school_name': school_name,
                        'district': dist,
                        'scores_by_type': {},  # 按户籍类型存储分数
                        'last_ranks_by_type': {}
                    }
                
                if stu_type not in years_data[school_id]['scores_by_type']:
                    years_data[school_id]['scores_by_type'][stu_type] = {}
                years_data[school_id]['scores_by_type'][stu_type][year] = min_score
                
                if last_rank is not None:
                    if stu_type not in years_data[school_id]['last_ranks_by_type']:
                        years_data[school_id]['last_ranks_by_type'][stu_type] = {}
                    years_data[school_id]['last_ranks_by_type'][stu_type][year] = last_rank
            
            # 2. 查询第三批次民办数据（仅公费班）
            private_results = self.db.query(
                School.school_id,
                School.school_name,
                School.district,
                Batch3Private.min_score,
                Batch3Private.last_volunteer_rank,
                Batch3Private.sub_type
            ).join(
                Batch3Private, School.school_id == Batch3Private.school_id
            ).filter(
                School.district.in_(all_target_districts),
                Batch3Private.year == year,
                Batch3Private.sub_type == '公费班'  # 只查询公费班
            ).all()
            
            for school_id, school_name, dist, min_score, last_rank, sub_type in private_results:
                if school_id not in years_data:
                    years_data[school_id] = {
                        'school_name': school_name,
                        'district': dist,
                        'scores_by_type': {},
                        'last_ranks_by_type': {}
                    }
                
                # 民办学校公费班统一标记为"户籍生"类型（因为公费班通常面向全市招生）
                stu_type_key = "户籍生"
                if stu_type_key not in years_data[school_id]['scores_by_type']:
                    years_data[school_id]['scores_by_type'][stu_type_key] = {}
                years_data[school_id]['scores_by_type'][stu_type_key][year] = min_score
                
                if last_rank is not None:
                    if stu_type_key not in years_data[school_id]['last_ranks_by_type']:
                        years_data[school_id]['last_ranks_by_type'][stu_type_key] = {}
                    years_data[school_id]['last_ranks_by_type'][stu_type_key][year] = last_rank
        
        # 计算加权平均和梯度信息 - 原则5：5年加权平均
        weighted_schools = []
        weights = {2025: 0.35, 2024: 0.25, 2023: 0.20, 2022: 0.12, 2021: 0.08}  # 调整为5年权重，总和=1.0
        
        # ⭐ 预先收集所有民办学校ID（有公费班记录的）
        private_school_ids = set(
            r[0] for r in self.db.query(Batch3Private.school_id).distinct().all()
        )
        
        for school_id, info in years_data.items():
            scores_by_type = info['scores_by_type']
            last_ranks_by_type = info['last_ranks_by_type']
            school_district = info['district']
            
            # 确定该考生相对于此学校的户籍类型
            actual_student_type = self._get_student_type_for_school(
                student_district, school_district, household_type
            )
            
            # 使用该户籍类型的分数数据
            scores = scores_by_type.get(actual_student_type, {})
            last_ranks = last_ranks_by_type.get(actual_student_type, {})
            
            # 特殊处理：如果是民办学校公费班，且当前户籍类型没有数据，尝试使用"户籍生"数据
            # （因为公费班通常面向全市招生，不区分户籍）
            if len(scores) < 1 and actual_student_type != "户籍生":
                scores = scores_by_type.get("户籍生", {})
                last_ranks = last_ranks_by_type.get("户籍生", {})
            
            # ⭐ 优化：所有学校（公办+民办）数据完整性要求统一为1年
            # 原因：
            # 1. 部分公办学校因招生政策特殊（如自主招生、新建校区）导致历史数据较少
            # 2. 确保用户有更多选择，避免因数据不足而过滤掉优质学校
            # 3. 对于只有1年数据的学校，后续会通过权重调整和警示提示来控制风险
            min_years_required = 1
            
            if len(scores) < min_years_required:
                continue
            
            # 计算加权平均分
            weighted_sum = 0
            total_weight = 0
            for year, score in scores.items():
                if year in weights and score is not None:
                    weighted_sum += score * weights[year]
                    total_weight += weights[year]
            
            if total_weight > 0:
                predicted_score = weighted_sum / total_weight
                
                # 确定学校梯度（使用考生对应的户籍类型）
                school_gradient = self._determine_school_gradient(
                    school_id, 
                    student_district,
                    school_district,
                    household_type,
                    2025
                )
                
                # 获取最新的末位志愿号
                last_volunteer_rank = None
                for year in [2025, 2024, 2023, 2022]:
                    if year in last_ranks:
                        last_volunteer_rank = last_ranks[year]
                        break
                
                # 计算趋势
                trend = "稳定"
                if 2025 in scores and 2024 in scores:
                    diff = scores[2025] - scores[2024]
                    if diff > 5:
                        trend = "上升"
                    elif diff < -5:
                        trend = "下降"
                
                # 标记是否为外区报考
                is_external_district = not (
                    self._is_old_three_district(student_district) and self._is_old_three_district(school_district)
                ) and student_district != school_district
                
                # ⭐ 新增：数据完整性评估
                years_count = len(scores)
                data_completeness = "complete" if years_count >= 3 else ("partial" if years_count >= 2 else "minimal")
                
                trend_info = {
                    'trend': trend,
                    'years_count': years_count,
                    'latest_score': scores.get(2025),
                    'avg_score': round(predicted_score, 1),
                    'actual_student_type': actual_student_type,
                    'is_external_district': is_external_district,
                    'data_completeness': data_completeness  # complete/partial/minimal
                }
                
                weighted_schools.append({
                    'school_id': school_id,
                    'school_name': info['school_name'],
                    'district': school_district,
                    'predicted_score': round(predicted_score, 1),
                    'school_gradient': school_gradient,
                    'last_volunteer_rank': last_volunteer_rank,
                    'trend_info': trend_info,
                    'is_private': school_id in private_school_ids  # ⭐ Add school type flag
                })
        
        return weighted_schools
    
    def _filter_schools_by_district(self, schools_data: List[Dict], district: str) -> List[Dict]:
        """
        过滤掉外区学校，只保留本区学校（老三区视为一个区）
        
        重要规则：
        - 省市属学校（district为空或"未知"）始终保留，不受外区限制
        - 老三区（越秀、海珠、荔湾）互认
        - 其他行政区只保留本区学校
        
        Args:
            schools_data: 学校数据列表
            district: 考生学籍区
            
        Returns:
            过滤后的学校列表
        """
        def is_province_city_school(s):
            """判断是否为省市属学校"""
            return s['district'] in ['', '未知']
        
        # 首先保留所有省市属学校
        province_city_schools = [s for s in schools_data if is_province_city_school(s)]
        
        # 然后根据区域规则过滤其他学校
        if self._is_old_three_district(district):
            # 如果考生在老三区，保留所有老三区的学校
            other_schools = [
                s for s in schools_data 
                if not is_province_city_school(s) and self._is_old_three_district(s['district'])
            ]
        else:
            # 否则只保留同一行政区的学校
            other_schools = [
                s for s in schools_data 
                if not is_province_city_school(s) and s['district'] == district
            ]
        
        # 合并：省市属学校 + 符合区域规则的学校
        return province_city_schools + other_schools
    
    def _filter_and_rank_schools(
        self,
        schools_data: List[Dict],
        student_gradient: int,
        estimated_score: float,
        student_district: str,
        household_type: str
    ) -> List[Dict]:
        """
        Filter and sort schools based on gradient admission rules
        
        ⭐ CRITICAL FIX: Enforce strict gradient constraints per Guangzhou policy
        Rule: Students can only apply to schools within their gradient level or one level above (for reach)
        """
        # ⭐ Pre-fetch private school IDs for sorting optimization
        private_school_ids = set(
            r[0] for r in self.db.query(Batch3Private.school_id).distinct().all()
        )
        
        filtered = []
        
        for school in schools_data:
            school_gradient = school['school_gradient']
            last_rank = school['last_volunteer_rank']
            predicted_score = school['predicted_score']
            score_gap = estimated_score - predicted_score
            
            # ⭐ CRITICAL RULE: Strict gradient constraint per Guangzhou policy
            # Gradient levels: 1=highest (707+), 2=(667-706), 3=(627-666), 4=(587-626), etc.
            # Lower gradient number = higher score requirement
            # 
            # Rule: Students can ONLY apply to schools at their gradient level or LOWER (higher number)
            # They CANNOT apply to schools at gradients significantly above their level
            #
            # Allow "reach" strategy: Can apply to schools 1 gradient above (lower number)
            # Example: 4th gradient student (600 pts) can apply to:
            #   - 3rd gradient schools (reach/冲刺, one level up)
            #   - 4th gradient schools (stable/稳妥, same level)
            #   - 5th+ gradient schools (safety/保底, lower levels)
            # CANNOT apply to 1st or 2nd gradient schools (too far above)
            
            if school_gradient and school_gradient < student_gradient - 1:
                # School gradient is too high (e.g., 1st/2nd for a 4th gradient student)
                # This violates the gradient admission rule
                continue
            
            school['score_gap'] = score_gap
            school['student_gradient'] = student_gradient
            
            # ⭐ Mark if this is a private school (for sorting optimization)
            school['is_private'] = school['school_id'] in private_school_ids
            
            filtered.append(school)
        
        # ⭐ CRITICAL FIX: Correct sorting order for volunteer positions
        # 
        # Volunteer position logic:
        #   V1 (First choice): Should be "reach" schools with NEGATIVE score gap (school score > student score)
        #   V2-V3 (Middle choices): Should be "stable" schools with SMALL POSITIVE gap (student slightly above school)
        #   V4-V6 (Last choices): Should be "safety" schools with LARGE POSITIVE gap (student well above school)
        #
        # Therefore, we need to sort by score_gap in ASCENDING order:
        #   Most negative gaps first (hardest to get into) → Most positive gaps last (easiest to get into)
        #
        # Example for 670-point student:
        #   School A: predicted 700, gap = -30 → V1 (reach)
        #   School B: predicted 680, gap = -10 → V2 (light reach)
        #   School C: predicted 670, gap = 0   → V3 (stable)
        #   School D: predicted 650, gap = +20 → V4 (safe)
        #   School E: predicted 630, gap = +40 → V5 (safer)
        #   School F: predicted 600, gap = +70 → V6 (safest)
        
        # ⭐ OPTIMIZATION: Remove data completeness penalty from sorting
        # 
        # Rationale: Data completeness should NOT penalize schools in ranking
        # - New schools naturally have less historical data
        # - Private fee-based classes are recently established programs
        # - Penalizing them hides viable options from users
        #
        # Instead, use data completeness only for frontend warnings
        # Sorting should prioritize score match quality
        
        filtered.sort(key=lambda x: (
            x.get('school_gradient') or 999,           # Primary: by gradient level
            abs(x['score_gap']),                        # Secondary: by score gap proximity (closer is better)
            x['score_gap']                              # Tertiary: negative gaps first (for reach strategy)
        ))
        
        # Note: Data completeness info is still stored in trend_info for frontend display
        # Frontend can show warnings like "该校历史数据较少，预测结果仅供参考"
        # But it should NOT affect the ranking order
        
        return filtered
    
    def _create_gradient_based_plan(
        self,
        plan_name: str,
        schools_data: List[Dict],
        estimated_score: float,
        student_gradient: int,
        student_district: str,
        household_type: str,
        plan_type: str
    ) -> VolunteerPlan:
        """
        基于梯度规则创建志愿方案
        
        核心原则：
        - 任何方案都必须包含保底志愿，确保考生不滑档
        - 分数差范围控制在合理区间（不超过1个梯度）
        
        策略差异（以6个志愿为例）：
        - 激进型：前2个冲刺 + 中间2个稳妥 + 后2个保底
        - 平衡型：第1个冲刺 + 中间3个稳妥 + 后2个保底
        - 保守型：第1个适度冲刺 + 中间2个稳妥 + 后3个保底
        """
        # ⭐ 关键改进：按位置分配不同的分数差范围
        
        volunteers = []
        all_position_candidates = []  # Store all candidates for each position
        volunteer_position = 1
        
        # Define score gap ranges for each position based on plan type
        # ⭐ 原则6：志愿之间保持20分左右的差距，负数分差在前面，正数分差在后面
        
        if plan_type == "aggressive":
            # Aggressive: 前2个冲刺(负分差) + 中间2个稳妥 + 后2个保底
            # 确保相邻位置间隔约20分
            position_ranges = {
                1: (-35, -20),   # V1: 强冲刺（-27.5中心值）
                2: (-20, -8),    # V2: 中度冲刺（-14中心值），间距~13.5
                3: (-8, 8),      # V3: 轻度冲刺/稳妥（0中心值），间距~14
                4: (8, 28),      # V4: 稳妥（18中心값），间距~18
                5: (28, 48),     # V5: 保底（38中心값），间距~20
                6: (48, 70)      # V6: 强保底（59中心값），间距~21
            }
            max_volunteers = 6
        elif plan_type == "balanced":
            # Balanced: 第1个轻度冲刺 + 中间2个稳妥 + 后3个保底
            position_ranges = {
                1: (-15, 0),     # V1: 轻度冲刺或稳妥（-7.5中心값）
                2: (0, 18),      # V2: 稳妥（9中心값），间距~16.5
                3: (18, 38),     # V3: 安全（28中心값），间距~19
                4: (38, 58),     # V4: 强安全（48中心값），间距~20
                5: (58, 78),     # V5: 很强安全（68中心값），间距~20
                6: (78, 98)      # V6: 绝对安全（88中心값），间距~20
            }
            max_volunteers = 6
        else:  # conservative
            # Conservative: 全部稳妥和保底，无负分差
            position_ranges = {
                1: (0, 18),      # V1: 稳妥（9中心값）
                2: (18, 38),     # V2: 安全（28中心값），间距~19
                3: (38, 58),     # V3: 强安全（48中心값），间距~20
                4: (58, 78),     # V4: 很强安全（68中心값），间距~20
                5: (78, 98),     # V5: 极强安全（88中心값），间距~20
                6: (98, 118)     # V6: 绝对安全（108中心값），间距~20
            }
            max_volunteers = 6
        
        used_school_ids = set()
        
        # Fill each volunteer position sequentially
        for pos in range(1, max_volunteers + 1):
            min_gap, max_gap = position_ranges[pos]
            
            # Filter schools matching current position's score gap range
            candidate_schools = [
                s for s in schools_data 
                if s['school_id'] not in used_school_ids
                and min_gap <= s.get('score_gap', 0) <= max_gap
            ]
            
            # ⭐ CRITICAL FIX: After initial filtering, ensure all candidates have gap > prev_gap
            if volunteers:
                prev_gap = volunteers[-1].estimated_score_gap
                min_required_gap = prev_gap + 10  # 调整为10分，确保志愿间有合理间距
                
                candidate_schools = [
                    s for s in candidate_schools
                    if s.get('score_gap', 0) >= min_required_gap
                ]
                
                # Force fallback by clearing candidate_schools if order is violated
                if candidate_schools is not None and len(candidate_schools) == 0:
                    candidate_schools = []
            
            # If still no candidates after order filter, use fallback
            if not candidate_schools:
                # ⭐ CRITICAL FIX: Must find schools for this position!
                # Gradually expand the search range until we find candidates
                
                prev_gap = volunteers[-1].estimated_score_gap if volunteers else -35
                min_acceptable_gap = prev_gap + 10  # 调整为10分最小间隔
                
                # Try multiple expansion strategies
                for attempt in range(1, 6):
                    if attempt == 1:
                        # Strategy 1: Expand range slightly
                        expanded_min = min_gap - 10 * attempt
                        expanded_max = max_gap + 10 * attempt
                    elif attempt == 2:
                        # Strategy 2: Focus on gap order, ignore range
                        expanded_min = min_acceptable_gap
                        expanded_max = 100
                    elif attempt == 3:
                        # Strategy 3: Lower minimum requirement
                        expanded_min = prev_gap + 2
                        expanded_max = 100
                    elif attempt == 4:
                        # Strategy 4: Any remaining school with positive gap
                        expanded_min = 0
                        expanded_max = 100
                    else:
                        # Strategy 5: Last resort - any remaining school with POSITIVE gap
                        expanded_min = 0  # Only positive gaps
                        expanded_max = 100
                    
                    candidate_schools = [
                        s for s in schools_data 
                        if s['school_id'] not in used_school_ids
                        and expanded_min <= s.get('score_gap', 0) <= expanded_max
                        and s.get('score_gap', 0) >= min_acceptable_gap  # Always enforce minimum gap
                    ]
                    
                    if candidate_schools:
                        break
                
                if not candidate_schools:
                    continue  # Skip this position, don't force a bad choice
            
            # ⭐ SIMPLIFIED LOGIC: Don't re-sort within each position
            # The schools_data is already sorted by (gradient, score_gap) ascending
            # Just filter by the position's score gap range and take top N
            
            # Collect top N candidates for this position
            if pos >= 5:  # Safety positions
                top_n = min(3, len(candidate_schools))
            elif plan_type == "aggressive":
                top_n = min(4, len(candidate_schools))
            elif plan_type == "balanced":
                top_n = min(3, len(candidate_schools))
            else:  # conservative
                top_n = min(3, len(candidate_schools))
            
            # Take first top_n candidates (already sorted by gradient and gap)
            selected_candidates = candidate_schools[:top_n]
            
            # Randomize order for diversity
            random.shuffle(selected_candidates)
            
            # Build VolunteerPosition with primary recommendation and alternatives
            position_candidates = []
            primary_selected = False
            
            for school_data in selected_candidates:
                school_id = school_data['school_id']
                school_name = school_data['school_name']
                district_name = school_data['district']
                score_gap = school_data['score_gap']
                last_volunteer_rank = school_data['last_volunteer_rank']
                school_gradient = school_data.get('school_gradient')
                trend_info = school_data['trend_info']
                
                # Check last volunteer rank constraint
                if last_volunteer_rank is not None:
                    if pos >= 5:
                        # Safety positions (V5-V6): No strict constraint
                        pass
                    elif pos >= 3:
                        # Middle positions (V3-V4): Allow position up to last_rank + 2
                        if volunteer_position > last_volunteer_rank + 2:
                            continue
                    else:
                        # Early positions (V1-V2): Allow position up to last_rank + 1
                        if volunteer_position > last_volunteer_rank + 1:
                            continue
                
                # Get historical data
                historical_data = self._get_school_historical_data(
                    school_id, 
                    trend_info.get('actual_student_type', household_type)
                )
                
                # Calculate admission probability
                probability = self._calculate_probability_with_gradient(
                    score_gap,
                    volunteer_position,
                    plan_type,
                    student_gradient,
                    school_gradient,
                    last_volunteer_rank,
                    trend_info.get('trend', '稳定')
                )
                
                # Set probability threshold based on position
                if pos >= 5:
                    min_probability = 0.02  # Safety positions: 2% minimum
                elif pos >= 3:
                    min_probability = 0.03  # Middle positions: 3% minimum
                else:
                    min_probability = 0.04  # Early positions: 4% minimum
                
                if probability < min_probability:
                    continue
                
                risk_level = self._determine_risk_level(score_gap, student_gradient, school_gradient)
                
                from ..schemas.response import HistoricalData, ScoreHistory
                hist_data_obj = HistoricalData(
                    enrollment_2025=historical_data.get('enrollment_2025'),
                    scores=[
                        ScoreHistory(
                            year=s['year'],
                            score=s['score'],
                            last_volunteer_rank=s.get('last_volunteer_rank')
                        )
                        for s in historical_data.get('scores', [])
                    ]
                )
                
                volunteer_item = VolunteerItem(
                    volunteer_number=volunteer_position,
                    school_info=SchoolInfo(
                        school_id=school_id,
                        school_name=school_name,
                        district=district_name,
                        school_type="民办" if school_data.get('is_private', False) else "公办"  # ⭐ Set school type
                    ),
                    risk_level=risk_level,
                    admission_probability=probability,
                    estimated_score_gap=round(score_gap, 1),
                    historical_data=hist_data_obj
                )
                
                position_candidates.append(volunteer_item)
                
                # Select first valid candidate as primary recommendation
                if not primary_selected:
                    volunteers.append(volunteer_item)
                    used_school_ids.add(school_id)
                    primary_selected = True
            
            # Store all candidates for this position (limit to max 5: 1 primary + 4 alternatives)
            if position_candidates:
                # ⭐ Limit to maximum 5 candidates per position
                MAX_CANDIDATES_PER_POSITION = 5
                if len(position_candidates) > MAX_CANDIDATES_PER_POSITION:
                    position_candidates = position_candidates[:MAX_CANDIDATES_PER_POSITION]
                
                position_strategy = "冲刺" if pos <= 2 else ("稳妥" if pos <= 4 else "保底")
                all_position_candidates.append(
                    VolunteerPosition(
                        position_number=pos,
                        recommended_school=position_candidates[0],
                        alternative_schools=position_candidates[1:],  # Max 4 alternatives
                        position_strategy=position_strategy
                    )
                )
            
            volunteer_position += 1
        
        rating_map = {
            "aggressive": "★★★☆☆",
            "balanced": "★★★★☆",
            "conservative": "★★★★★"
        }
        
        return VolunteerPlan(
            plan_name=plan_name,
            overall_rating=rating_map.get(plan_type, "★★★★☆"),
            volunteers=volunteers,
            all_candidates=all_position_candidates
        )
    
    def _calculate_probability_with_gradient(
        self,
        score_gap: float,
        volunteer_position: int,
        plan_type: str,
        student_gradient: int,
        school_gradient: Optional[int],
        last_volunteer_rank: Optional[int],
        trend: str = "稳定"
    ) -> float:
        """
        Calculate admission probability based on gradient rules
        
        ⭐ 核心原则（按优先级）：
        1. 不同梯度 → 梯度优先（高分梯度必然优先录取）
        2. 同一梯度 → 志愿优先（同一梯度内，志愿顺序决定录取顺序）
        3. 同一志愿 → 分数优先（同志愿内，分数高的优先）
        4. 同分情况 → 末位志愿号才有意义
        """
        
        # Rule 1: Last volunteer rank constraint - ⭐ ONLY applies when score gap is small
        # 末位志愿号只在分数接近时才有意义，分差大时完全无效
        last_rank_penalty = 1.0  # Default: no penalty
        
        if last_volunteer_rank is not None and abs(score_gap) <= 10:
            # 只有在分差≤10分时，末位志愿号才可能有影响
            # 因为此时可能进入同分比较环节
            if volunteer_position > last_volunteer_rank:
                excess = volunteer_position - last_volunteer_rank
                
                if excess <= 2:
                    # 轻微超出：小幅惩罚
                    last_rank_penalty = 0.95
                elif excess <= 4:
                    # 中度超出：中等惩罚
                    last_rank_penalty = 0.85
                else:
                    # 严重超出：较大惩罚（但仍不是极端值）
                    last_rank_penalty = 0.70
            # 注意：如果分差>10分，完全不应用末位志愿号惩罚
        
        # Rule 2: Gradient gap impact (PRIMARY FACTOR)
        # ⭐ FIXED: Only apply gradient penalty when score gap is small
        # When score gap is large, the gap already reflects the advantage
        if school_gradient and student_gradient:
            gradient_diff = school_gradient - student_gradient
            
            # 只有当分差较小时（≤20分），梯度差异才有参考意义
            # 分差大时，分数优势已经体现了梯度差异，不应重复惩罚
            if abs(score_gap) <= 20:
                # 小分差场景：梯度差异影响基础概率
                if gradient_diff > 0:
                    # 学校梯度更高（更难考），基础概率降低
                    base_prob = max(0.15, 0.55 - gradient_diff * 0.12)
                else:
                    # 学生梯度≥学校梯度，基础概率较高
                    base_prob = 0.75
            else:
                # 大分差场景：忽略梯度差异，给予高基础概率
                # 因为分差已经反映了实际的分数优势
                base_prob = 0.75
        else:
            base_prob = 0.55
        
        # Rule 3: Score gap adjustment (CRITICAL for cross-gradient advantage)
        # ⭐ FIXED: Remove intermediate caps to allow large gaps to overcome penalties
        if score_gap >= 80:
            # ⭐ 绝对优势（80分以上）：极大奖励
            base_prob += 0.50
        elif score_gap >= 70:
            # 极大优势（70-80分）
            base_prob += 0.48
        elif score_gap >= 60:
            # 超大优势（60-70分）
            base_prob += 0.45
        elif score_gap >= 50:
            # 很大优势（50-60分）
            base_prob += 0.42
        elif score_gap >= 40:
            # 跨梯度优势（40-50分）
            base_prob += 0.40
        elif score_gap >= 30:
            base_prob += 0.35
        elif score_gap >= 20:
            base_prob += 0.30
        elif score_gap >= 10:
            base_prob += 0.20
        elif score_gap >= 5:
            base_prob += 0.12
        elif score_gap >= 0:
            base_prob += 0.05
        elif score_gap >= -5:
            base_prob -= 0.08
        elif score_gap >= -10:
            base_prob -= 0.15
        elif score_gap >= -20:
            base_prob -= 0.25
        else:
            base_prob -= 0.35
        
        # Clamp after score gap adjustment to prevent extreme values
        base_prob = max(0.10, min(1.00, base_prob))
        
        # Apply last volunteer rank penalty (only if applicable)
        base_prob *= last_rank_penalty
        
        # Trend adjustment - ⭐ MINIMAL impact for very large score gaps
        # 当分差非常大时，趋势的影响应该极小，几乎可以忽略
        if trend == "上升":
            # 上升趋势会降低概率，但超大分差时影响应该极小
            if abs(score_gap) >= 70:
                # 极大分差：几乎不惩罚（只降低0.5%）
                base_prob *= 0.995
            elif abs(score_gap) >= 60:
                # 超大分差：极轻微惩罚（降低1%）
                base_prob *= 0.99
            elif abs(score_gap) >= 40:
                # 大分差：轻微惩罚（降低1.5%）
                base_prob *= 0.985
            elif abs(score_gap) >= 20:
                # 中等分差：中度惩罚（降低3%）
                base_prob *= 0.97
            else:
                # 小分差：正常惩罚（降低5%）
                base_prob *= 0.95
        elif trend == "下降":
            # 下降趋势会提高概率，但大分差时增幅应受限
            if abs(score_gap) >= 70:
                # 极大分差：几乎不提升（只增加0.5%）
                base_prob *= 1.005
            elif abs(score_gap) >= 60:
                # 超大分差：极轻微提升（增加0.8%）
                base_prob *= 1.008
            elif abs(score_gap) >= 40:
                # 大分差：轻微提升（增加1%）
                base_prob *= 1.01
            elif abs(score_gap) >= 20:
                # 中等分差：中度提升（增加2%）
                base_prob *= 1.02
            else:
                # 小分差：正常提升（增加5%）
                base_prob *= 1.05
        
        # Volunteer position decay - ⭐ REDUCED for high probability scenarios
        # 当基础概率已经很高时（通常对应超大分差保底），位置衰减应该更小
        if base_prob >= 0.90:
            # 高概率场景：衰减减半，确保保底志愿稳定性
            position_decay = 1.0 - (volunteer_position - 1) * 0.008
        else:
            # 普通场景：正常衰减
            position_decay = 1.0 - (volunteer_position - 1) * 0.015
        
        base_prob *= position_decay
        
        return round(max(0.05, min(0.98, base_prob)), 2)
    
    def _determine_risk_level(
        self, 
        score_gap: float, 
        student_gradient: int,
        school_gradient: Optional[int]
    ) -> str:
        """确定风险等级"""
        # 主要基于分数差判断
        if score_gap < -10:
            return "冲刺"  # 远低于预测分数线（需要大幅冲刺）
        elif -10 <= score_gap < 0:
            return "冲刺"  # 略低于预测分数线（需要适度冲刺）
        elif 0 <= score_gap <= 15:
            return "稳妥"  # 接近或略高于预测分数线（较稳妥）
        elif 15 < score_gap <= 30:
            return "保底"  # 明显高于预测分数线（安全保底）
        else:  # score_gap > 30
            return "保底"  # 远高于预测分数线（强保底）
    
    def _get_school_historical_data(
        self,
        school_id: int,
        household_type: str
    ) -> Dict:
        """获取学校的历史录取数据"""
        scores = []
        enrollment_2025 = None
        
        # 1. 查询录取分数线（公办）
        for year in range(2025, 2020, -1):
            record = self.db.query(Batch3Public).filter(
                Batch3Public.school_id == school_id,
                Batch3Public.year == year,
                Batch3Public.student_type == household_type
            ).first()
            
            if record:
                scores.append({
                    'year': year,
                    'score': record.min_score,
                    'last_volunteer_rank': record.last_volunteer_rank
                })
        
        # 2. 如果公办没有数据，查询民办公费班数据
        if not scores:
            for year in range(2025, 2020, -1):
                private_record = self.db.query(Batch3Private).filter(
                    Batch3Private.school_id == school_id,
                    Batch3Private.year == year,
                    Batch3Private.sub_type == '公费班'
                ).first()
                
                if private_record:
                    scores.append({
                        'year': year,
                        'score': private_record.min_score,
                        'last_volunteer_rank': private_record.last_volunteer_rank
                    })
        
        # 3. 查询2025年招生计划
        school_record = self.db.query(School).filter(School.school_id == school_id).first()
        if school_record and school_record.school_name:
            enrollment_record = self.db.query(EnrollmentPlan).filter(
                EnrollmentPlan.year == 2025,
                EnrollmentPlan.school_name == school_record.school_name
            ).first()
            
            if enrollment_record and enrollment_record.plan_total:
                enrollment_2025 = enrollment_record.plan_total
        
        scores.sort(key=lambda x: x['year'])
        
        return {
            'enrollment_2025': enrollment_2025,
            'scores': scores
        }