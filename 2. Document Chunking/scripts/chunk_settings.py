"""P017 exploratory configuration; frozen P007 presets remain immutable."""
import hashlib,json,math
from experiment_common import need

METHODS = {
    'fixed': dict(label='고정 크기',minimum=100,maximum=2000,default=400,overlap_default=80),
    'recursive': dict(label='재귀 분할',minimum=100,maximum=2000,default=400,overlap_default=0),
    'structure': dict(label='구조 기반',minimum=100,maximum=2000,default=400,overlap_default=0),
    'semantic': dict(label='의미 기반',minimum=400,maximum=2000,default=400,overlap_default=0),
    'llm': dict(label='LLM 기반',minimum=400,maximum=1200,default=800,overlap_default=0),
}
LIMITS = dict(methods=METHODS,overlap_max=400,threshold=dict(minimum=0,maximum=2,default=.25),
              top_k=dict(minimum=1,maximum=20,default=5),budget_chars=dict(minimum=1,maximum=24000,default=8000),candidate_limit=20)

def normalize(value):
    need(isinstance(value,dict),'invalid_config','청킹 설정은 객체여야 합니다.')
    method=value.get('method');need(isinstance(method,str) and method in METHODS,'invalid_config','청킹 방식을 선택하세요.')
    canonical=value.get('profile')=='custom-v1'
    size_key='size_chars' if not canonical or method=='fixed' else 'base_max_chars'
    keys={'method',size_key,'overlap_chars'}|({'distance_threshold'} if method=='semantic' else set())
    if canonical:
        keys|={'id','profile'}
        if method!='fixed':keys|={'overlap_policy'}
        if method=='semantic':keys|={'minimum_chars'}
        if method=='llm':keys|={'preferred_chars'}
    need(set(value)==keys,'invalid_config','설정에 누락되거나 적용되지 않는 필드가 있습니다.')
    size=value[size_key];overlap=value['overlap_chars'];bounds=METHODS[method]
    need(type(size) is int and bounds['minimum']<=size<=bounds['maximum'],'invalid_config',f"크기는 {bounds['minimum']}~{bounds['maximum']}자 정수여야 합니다.")
    maximum=min(400,size-(100 if method=='fixed' else 1))
    need(type(overlap) is int and 0<=overlap<=maximum,'invalid_config',f'오버랩은 0~{maximum}자 정수여야 합니다.')
    out=dict(profile='custom-v1',method=method,**{('size_chars' if method=='fixed' else 'base_max_chars'):size},overlap_chars=overlap)
    if method!='fixed':out['overlap_policy']='post_partition_left_extension_v1'
    if method=='semantic':
        threshold=value['distance_threshold'];need(type(threshold) in (int,float) and math.isfinite(threshold) and 0<=threshold<=2,'invalid_config','의미 거리 임계값은 0~2의 유한 숫자여야 합니다.')
        out.update(distance_threshold=float(threshold),minimum_chars=100)
    if method=='llm':out['preferred_chars']=[200,400]
    digest=hashlib.sha256(json.dumps(out,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()[:16]
    out={'id':f'custom-{method}-{digest}',**out}
    need(not canonical or out==value,'invalid_config','저장 설정의 ID/고정 매개변수가 일치하지 않습니다.')
    return out

def custom(value):return value.get('profile')=='custom-v1'

def without_overlap(cfg):
    if not custom(cfg):return cfg['method']+'-0'
    raw=dict(method=cfg['method'],size_chars=cfg.get('size_chars',cfg.get('base_max_chars')),overlap_chars=0)
    if cfg['method']=='semantic':raw['distance_threshold']=cfg['distance_threshold']
    return normalize(raw)
