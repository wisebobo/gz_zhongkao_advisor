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
from ..schemas.response import VolunteerResponse, VolunteerPlan, VolunteerItem, SchoolInfo

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
        1. 如果考生和学校在老三区内，视为户籍生（老三区互认）
        2. 如果考生和学校在同一行政区，视为户籍生
        3. 其他情况，视为外区生/非户籍生
        
        Args:
            student_district: 考生学籍区
            school_district: 学校所在区
            household_type: 考生户籍类型
            
        Returns:
            "户籍生" 或 "非户籍生"
        """
        # 规则1：老三区互认
        if self._is_old_three_district(student_district) and self._is_old_three_district(school_district):
            return "户籍生"
        
        # 规则2：同一行政区
        if student_district == school_district:
            return "户籍生"
        
        # 规则3：跨区报考，视为外区生
        return "非户籍生"
    
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
        
        # 查询近4年的录取数据（包含公办和民办公费班）
        years_data = {}
        for year in [2025, 2024, 2023, 2022]:
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
        
        # 计算加权平均和梯度信息
        weighted_schools = []
        weights = {2025: 0.4, 2024: 0.3, 2023: 0.2, 2022: 0.1}
        
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
            if len(scores) < 2 and actual_student_type != "户籍生":
                scores = scores_by_type.get("户籍生", {})
                last_ranks = last_ranks_by_type.get("户籍生", {})
            
            if len(scores) < 2:
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
                
                trend_info = {
                    'trend': trend,
                    'years_count': len(scores),
                    'latest_score': scores.get(2025),
                    'avg_score': round(predicted_score, 1),
                    'actual_student_type': actual_student_type,
                    'is_external_district': is_external_district
                }
                
                weighted_schools.append({
                    'school_id': school_id,
                    'school_name': info['school_name'],
                    'district': school_district,
                    'predicted_score': round(predicted_score, 1),
                    'school_gradient': school_gradient,
                    'last_volunteer_rank': last_volunteer_rank,
                    'trend_info': trend_info
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
        根据梯度投档规则筛选和排序学校
        """
        filtered = []
        
        for school in schools_data:
            school_gradient = school['school_gradient']
            last_rank = school['last_volunteer_rank']
            predicted_score = school['predicted_score']
            score_gap = estimated_score - predicted_score
            
            # 规则1：学校梯度不能高于考生梯度太多
            if school_gradient and school_gradient > student_gradient + 2:
                continue
            
            school['score_gap'] = score_gap
            school['student_gradient'] = student_gradient
            
            filtered.append(school)
        
        # 排序：优先按梯度，再按分数差
        filtered.sort(key=lambda x: (
            x.get('school_gradient') or 999,
            -x['score_gap']
        ))
        
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
        volunteer_position = 1
        
        # ⭐ 关键改进：在6个志愿的限制内，强化保底机制
        # 广州中考第三批次最多可填报6个志愿，我们需要在这6个志愿中合理分配"冲稳保"比例
        
        # 根据方案类型定义每个位置的分数差范围
        if plan_type == "aggressive":
            # 激进型：前2冲刺 + 中间2稳妥 + 后2强保底
            position_ranges = {
                1: (-25, -8),   # 第1志愿：冲刺（较难）
                2: (-20, -5),   # 第2志愿：冲刺（适度）
                3: (-5, 8),     # 第3志愿：稳妥（接近预测线）
                4: (0, 15),     # 第4志愿：稳妥（略高于预测线）
                5: (15, 40),    # 第5志愿：强保底（应对小幅失误）
                6: (30, 65)     # 第6志愿：超强保底（应对较大失误，确保有书读）⭐ 扩大到+65分
            }
            max_volunteers = 6
        elif plan_type == "balanced":
            # 平衡型：第1个轻度冲刺 + 中间2稳妥 + 后3保底
            position_ranges = {
                1: (-8, 5),     # 第1志愿：轻度冲刺或接近预测线
                2: (0, 12),     # 第2志愿：稳妥
                3: (5, 20),     # 第3志愿：稳妥
                4: (15, 35),    # 第4志愿：保底
                5: (25, 50),    # 第5志愿：强保底
                6: (40, 70)     # 第6志愿：超强保底（即使低40-50分也有书读）⭐ 扩大到+70分
            }
            max_volunteers = 6
        else:  # conservative
            # 保守型：全部稳妥和保底，最大化兜底能力
            position_ranges = {
                1: (0, 12),     # 第1志愿：稳妥（不低于预测线）
                2: (5, 20),     # 第2志愿：稳妥偏保底
                3: (12, 30),    # 第3志愿：保底
                4: (20, 45),    # 第4志愿：强保底
                5: (35, 60),    # 第5志愿：超强保底
                6: (50, 85)     # 第6志愿：绝对保底（即使低50-60分也能录取）⭐ 扩大到+85分
            }
            max_volunteers = 6
        
        used_school_ids = set()
        
        # 按志愿位置依次填充
        for pos in range(1, max_volunteers + 1):
            min_gap, max_gap = position_ranges[pos]
            
            # 筛选符合当前志愿位置分数差范围的学校
            candidate_schools = [
                s for s in schools_data 
                if s['school_id'] not in used_school_ids
                and min_gap <= s.get('score_gap', 0) <= max_gap
            ]
            
            # 如果该位置没有合适的学校，逐步扩大范围直到找到为止
            expand_attempts = 0
            while not candidate_schools and expand_attempts < 3:
                expand_attempts += 1
                expanded_min = max(min_gap - 15 * expand_attempts, -50)
                expanded_max = min(max_gap + 15 * expand_attempts, 120)
                candidate_schools = [
                    s for s in schools_data 
                    if s['school_id'] not in used_school_ids
                    and expanded_min <= s.get('score_gap', 0) <= expanded_max
                ]
            
            if not candidate_schools:
                # 实在找不到，使用全局最稳妥的学校作为保底
                fallback_schools = [
                    s for s in schools_data 
                    if s['school_id'] not in used_school_ids
                    and s.get('score_gap', 0) > 50  # 选择分数差>50的超稳妥学校
                ]
                if fallback_schools:
                    fallback_schools.sort(key=lambda x: x.get('score_gap', 0), reverse=True)
                    candidate_schools = fallback_schools[:2]
                else:
                    continue  # 真的没有可选学校了
            
            # 根据位置排序
            if pos <= 2:  # 冲刺位置：从难到易
                candidate_schools.sort(key=lambda x: x.get('score_gap', 0))
            elif pos >= 5:  # 保底位置（第5-6志愿）：从易到难（越稳越好）⭐ 调整为>=5
                candidate_schools.sort(key=lambda x: x.get('score_gap', 0), reverse=True)
            else:  # 稳妥位置（第3-4志愿）：接近预测线优先
                candidate_schools.sort(key=lambda x: abs(x.get('score_gap', 0)))
            
            # ⭐ 增加多样性：从前N个候选中随机选择（而非总是选第一个）
            # ⭐ 保底位置（第5-6志愿）减少随机性，确保稳定性
            if pos >= 5:  # 保底位置：只从前2个中选，确保最稳妥
                top_n = min(2, len(candidate_schools))
            elif plan_type == "aggressive":
                top_n = min(5, len(candidate_schools))
            elif plan_type == "balanced":
                top_n = min(3, len(candidate_schools))
            else:  # conservative
                top_n = min(2, len(candidate_schools))
            
            selected_candidates = candidate_schools[:top_n]
            
            # ⭐ 随机打乱候选顺序，增加多样性
            random.shuffle(selected_candidates)
            
            # 选择最佳学校
            for school_data in selected_candidates:
                school_id = school_data['school_id']
                school_name = school_data['school_name']
                district_name = school_data['district']
                score_gap = school_data['score_gap']
                last_volunteer_rank = school_data['last_volunteer_rank']
                school_gradient = school_data.get('school_gradient')
                trend_info = school_data['trend_info']
                
                # 检查末位志愿号约束
                # ⭐ 保底位置（第5-6志愿）放宽约束：即使末位志愿号较小，但分数差足够大时仍可考虑
                if last_volunteer_rank is not None:
                    if pos >= 5:
                        # 保底位置：只有当填报位置远大于末位志愿号时才排除（如第6志愿但末位志愿=1）
                        if volunteer_position > last_volunteer_rank + 2:
                            continue
                    else:
                        # 非保底位置：严格执行末位志愿号约束
                        if volunteer_position > last_volunteer_rank:
                            continue
                
                # 获取历史数据
                historical_data = self._get_school_historical_data(
                    school_id, 
                    trend_info.get('actual_student_type', household_type)
                )
                
                # 计算录取概率
                probability = self._calculate_probability_with_gradient(
                    score_gap,
                    volunteer_position,
                    plan_type,
                    student_gradient,
                    school_gradient,
                    last_volunteer_rank,
                    trend_info.get('trend', '稳定')
                )
                
                # ⭐ 保底志愿（第5-6志愿）降低概率阈值，确保能填满志愿
                if pos >= 5:
                    min_probability = 0.02  # 保底志愿：2%即可
                else:
                    min_probability = 0.05  # 其他志愿：5%
                
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
                
                volunteer = VolunteerItem(
                    volunteer_number=volunteer_position,
                    school_info=SchoolInfo(
                        school_id=school_id,
                        school_name=school_name,
                        district=district_name
                    ),
                    risk_level=risk_level,
                    admission_probability=probability,
                    estimated_score_gap=round(score_gap, 1),
                    historical_data=hist_data_obj
                )
                volunteers.append(volunteer)
                used_school_ids.add(school_id)
                volunteer_position += 1
                break  # 每个位置只选一个学校
        
        rating_map = {
            "aggressive": "★★★☆☆",
            "balanced": "★★★★☆",
            "conservative": "★★★★★"
        }
        
        return VolunteerPlan(
            plan_name=plan_name,
            overall_rating=rating_map.get(plan_type, "★★★★☆"),
            volunteers=volunteers
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
        基于梯度规则计算录取概率
        """
        # 规则1：末位志愿号约束
        if last_volunteer_rank is not None and volunteer_position > last_volunteer_rank:
            return 0.02
        
        # 规则2：梯度差距影响
        if school_gradient and student_gradient:
            gradient_diff = school_gradient - student_gradient
            if gradient_diff > 0:
                base_prob = max(0.1, 0.5 - gradient_diff * 0.15)
            else:
                base_prob = 0.7
        else:
            base_prob = 0.5
        
        # 规则3：分数差调整
        if score_gap >= 20:
            base_prob = min(base_prob + 0.3, 0.98)
        elif score_gap >= 10:
            base_prob = min(base_prob + 0.2, 0.90)
        elif score_gap >= 5:
            base_prob = min(base_prob + 0.1, 0.80)
        elif score_gap >= 0:
            base_prob = base_prob
        elif score_gap >= -5:
            base_prob = max(base_prob - 0.1, 0.3)
        elif score_gap >= -10:
            base_prob = max(base_prob - 0.2, 0.2)
        else:
            base_prob = max(base_prob - 0.3, 0.1)
        
        # 趋势调整
        if trend == "上升":
            base_prob *= 0.9
        elif trend == "下降":
            base_prob *= 1.1
        
        # 志愿位置轻微衰减
        position_decay = 1.0 - (volunteer_position - 1) * 0.02
        base_prob *= position_decay
        
        return round(max(0.02, min(0.98, base_prob)), 2)
    
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