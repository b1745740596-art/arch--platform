from django.db import migrations


STEP_KINDS = (
    'intake', 'emotion', 'intent', 'profile_update', 'stage_judge',
    'strategy_plan', 'rag_retrieve', 'llm_generate', 'guard', 'output', 'log',
)

DOCUMENTS = (
    ('环保与健康', 'craft', '儿童与孕妇家庭环保建议',
     '环保判断应以材料合格证明和入住前检测结果为准。优先核对板材、涂料、胶黏剂的执行标准，完成施工后充分通风，并委托有资质机构检测；不得承诺“零甲醛”。',
     ['环保健康', '甲醛', '儿童房']),
    ('预算与增项', 'objection', '控制增项的合同做法',
     '签约前应明确项目范围、品牌型号、工程量计算口径、允许增项的条件和书面审批流程。未获得客户书面确认的新增项目不应直接施工计费。',
     ['预算失控', '增项', '合同']),
    ('工期管理', 'craft', '工期节点与验收',
     '工期需要按拆改、水电、泥木、油漆、安装和竣工验收拆成节点，并明确材料到场、变更确认及延期责任。具体天数必须结合面积、施工范围和现场条件确认。',
     ['工期拖延', '验收', '施工']),
    ('报价口径', 'quote', '预方案报价边界',
     '线上预算仅用于方案方向比较，不是施工合同报价。正式报价需完成现场量房、工程量核对、材料型号确认和可施工校验，并将税费、管理费及可能发生的增项单独列明。',
     ['预算', '报价', '量房']),
    ('顾问话术', 'script', '犹豫时的回应',
     '先确认用户担心的具体风险，再提供可以核验的材料、节点或合同条款；允许用户比较和暂停，不使用虚假倒计时、库存或情感绑架。',
     ['犹豫', '不信任', '合规']),
)


def seed_talkbot(apps, schema_editor):
    TalkWorkflow = apps.get_model('talkbot', 'TalkWorkflow')
    TalkStep = apps.get_model('talkbot', 'TalkStep')
    KnowledgeBase = apps.get_model('talkbot', 'KnowledgeBase')
    KnowledgeDocument = apps.get_model('talkbot', 'KnowledgeDocument')

    workflow, _ = TalkWorkflow.objects.update_or_create(
        name='标准谈单流程',
        defaults={
            'description': '情绪/意图识别 → 画像更新 → 策略 → RAG → 回复 → 合规过滤',
            'is_default': True,
            'is_active': True,
            'stop_on_error': False,
        },
    )
    labels = {
        'intake': '接收输入', 'emotion': '情绪识别', 'intent': '意图识别',
        'profile_update': '更新画像', 'stage_judge': '阶段判断',
        'strategy_plan': '策略决策', 'rag_retrieve': '知识检索',
        'llm_generate': '生成回复', 'guard': '安全合规', 'output': '输出', 'log': '记录轨迹',
    }
    for index, kind in enumerate(STEP_KINDS, start=1):
        TalkStep.objects.update_or_create(
            workflow=workflow,
            kind=kind,
            defaults={
                'order': index * 10,
                'name': labels[kind],
                'params': {'limit': 3} if kind == 'rag_retrieve' else {},
                'is_active': True,
                'continue_on_error': True,
            },
        )

    for base_name, category, title, content, tags in DOCUMENTS:
        base, _ = KnowledgeBase.objects.update_or_create(
            name=base_name,
            defaults={'category': category, 'is_active': True},
        )
        KnowledgeDocument.objects.update_or_create(
            base=base,
            title=title,
            defaults={'content': content, 'tags': tags, 'priority': 20, 'is_active': True},
        )


class Migration(migrations.Migration):
    dependencies = [('talkbot', '0001_initial')]
    operations = [migrations.RunPython(seed_talkbot, migrations.RunPython.noop)]
