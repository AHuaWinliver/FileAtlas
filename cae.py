"""Built-in CAE templates and conservative filing policies. No AI calls."""
import json
import os
from pathlib import Path
import re
import uuid

SOLVER_EXTENSIONS = {'.cae', '.odb', '.sim', '.rst', '.res', '.op2', '.fem', '.inp', '.bdf', '.bin',
                     '.adm', '.acf', '.cmd', '.cas', '.dat', '.msh', '.cdb', '.wbpj', '.mechdb', '.db'}


def component(value):
    value = value.strip()
    if (not value or len(value) > 80 or value in ('.', '..') or re.search(r'[<>:"/\\|?*\x00-\x1f]', value)
            or value.endswith(('.', ' ')) or value.split('.')[0].upper() in
            {'CON', 'PRN', 'AUX', 'NUL', *('COM' + str(i) for i in range(1, 10)), *('LPT' + str(i) for i in range(1, 10))}):
        raise ValueError('名称不能包含 Windows 路径特殊字符或保留名称，且不得超过 80 字符')
    return value


def workspace_plan(root):
    entries = [('01_项目库', '工程项目容器；在此创建具体项目', False, False),
               ('02_公共资源库', '不属于具体项目的可复用工程资源', False, False),
               ('03_知识与方法', '通用工程知识与方法', False, False),
               ('99_已结项归档', '已结项工程整体归档区，不自动接收零散文件', False, True)]
    for name, description in [('材料数据库', '通用材料属性、材料卡片，不含具体项目试验数据'),
                              ('标准件与典型模型', '可复用标准件和通用模型资料'),
                              ('载荷谱与试验数据', '可复用通用载荷谱与试验资料'),
                              ('脚本与自动化工具', '通用脚本、宏、后处理自动化工具'),
                              ('报告与建模模板', '空白报告、建模模板，不是实际项目报告')]:
        entries.append(('02_公共资源库/' + name, description, True, False))
    for name in ('标准规范', '软件手册', '理论与论文', '分析方法与检查清单', '典型问题与经验'):
        entries.append(('03_知识与方法/' + name, '与具体项目无关的通用' + name, True, False))
    return entries


def project_plan(project_id, client, name, keywords=''):
    component(project_id)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,31}', project_id):
        raise ValueError('项目编号使用英文字母、数字、下划线或连字符，最多 32 字符')
    title = '_'.join((project_id, component(client), component(name)))
    context = f'项目编号：{project_id}；客户：{client}；项目：{name}；关键词：{keywords.strip()[:500]}。'
    entries = [(title, context + '项目容器', False, False)]
    groups = [
        ('00_项目管理', ['需求与任务书', '计划与会议', '技术沟通']),
        ('01_原始输入', ['原始CAD', '材料与试验数据', '载荷与边界条件']),
        ('02_模型准备', ['几何清理与简化', '网格与连接', '模型检查']),
        ('03_仿真任务', []),
        ('04_结果分析', ['曲线与数据', '云图与动画', '对比与验证']),
        ('05_报告与交付', ['报告草稿', '审核记录', '正式交付']),
        ('90_历史版本', [])]
    for group, children in groups:
        protected = group in ('03_仿真任务', '90_历史版本')
        entries.append((title + '/' + group, context + group, False, protected))
        for child in children:
            entries.append((title + '/' + group + '/' + child, context + '用途：' + child, True, False))
    for suffix in ('', '/输入', '/求解', '/日志'):
        entries.append((title + '/03_仿真任务/C001_基准工况' + suffix, context + '完整工况目录，禁止拆分整理', False, True))
    return entries


def apply_plan(store, root, entries, project_id=None, parent=None, extra_settings=None):
    if not Path(root).is_absolute():
        raise ValueError('工作空间必须使用绝对路径')
    root = Path(root).resolve()
    if root.is_relative_to(store.home) or store.home.is_relative_to(root):
        raise ValueError('工作空间不能与应用数据目录重叠')
    policies = store.get('category_policies', {})
    existing = {os.path.normcase(str(Path(c['destination']).resolve())): c for c in store.categories()}
    planned, ids = [], {}
    # Validate the complete plan before creating folders or changing the database.
    for relative, description, allowed, protected in entries:
        dest = (root / relative).resolve()
        if not dest.is_relative_to(root) or (dest.exists() and not dest.is_dir()):
            raise ValueError('保存地址发生冲突或通过链接跳出工作空间：' + str(dest))
        if any(Path(s).resolve().is_relative_to(dest) for s in store.get('sources', [])):
            raise ValueError('分类目录不能包含现有整理源：' + str(dest))
        old = existing.get(os.path.normcase(str(dest)))
        if old and old['id'] not in policies:
            raise ValueError('现有自定义分类占用了模板地址，请选择其他工作空间：' + str(dest))
        expected_parent = ids.get(str(Path(relative).parent).replace('\\', '/'), parent)
        if old and (old['parent'] != expected_parent or old['name'] != Path(relative).name):
            raise ValueError('现有分类与模板冲突：' + str(dest))
        cid = old['id'] if old else uuid.uuid4().hex
        ids[relative] = cid
        planned.append((cid, expected_parent, dest.name, str(dest), description, old is not None))
        if old is None:
            policies[cid] = dict(allow_files=allowed, protected=protected, project_id=project_id)
    for item in planned:
        Path(item[3]).mkdir(parents=True, exist_ok=True)
    with store.lock, store.db:
        for cid, pid, name, dest, description, exists in planned:
            if not exists:
                store.db.execute('INSERT INTO categories VALUES(?,?,?,?,?)', (cid, pid, name, dest, description))
        settings = dict(extra_settings or {}, category_policies=policies, cae_mode=True)
        for key, value in settings.items():
            store.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, json.dumps(value, ensure_ascii=False)))
    store.export_tree()
    return ids


def install_workspace(store, root):
    root = Path(root)
    if not root.is_absolute():
        raise ValueError('请选择工作空间的绝对路径')
    root = root.resolve()
    if root.is_relative_to(store.home) or store.home.is_relative_to(root):
        raise ValueError('工作空间不能与应用数据目录重叠')
    inbox = root / '00_待整理'
    workspaces = store.get('cae_workspaces', [])
    if str(root) in workspaces:
        raise ValueError('此工作空间已初始化，请直接新建工程项目')
    if inbox.exists() and not inbox.is_dir():
        raise ValueError('待整理路径已被同名文件占用')
    for path in (inbox, inbox / '下载与接收', inbox / '临时资料'):
        if not path.resolve().is_relative_to(root) or (path.exists() and not path.is_dir()):
            raise ValueError('待整理目录存在文件冲突或目录链接越界')
    # Validate existing source/destination overlap before creating the inbox.
    if any(inbox.is_relative_to(Path(c['destination']).resolve()) for c in store.categories()):
        raise ValueError('待整理目录位于已有分类目标内，请选择其他工作空间')
    sources = list(dict.fromkeys(store.get('sources', []) + [str(inbox)]))
    for child in ('下载与接收', '临时资料'):
        (inbox / child).mkdir(parents=True, exist_ok=True)
    ids = apply_plan(store, root, workspace_plan(root), extra_settings={
        'cae_workspaces': workspaces + [str(root)], 'sources': sources})
    roots = store.get('cae_workspace_roots', {})
    roots[str(root)] = ids['01_项目库']
    store.set('cae_workspace_roots', roots)
    store.event('CAE 模板', '工作空间已创建：' + str(root))
    return ids


def create_project(store, workspace, project_id, client, name, keywords=''):
    workspace = str(Path(workspace).resolve())
    if workspace not in store.get('cae_workspaces', []):
        raise ValueError('请先初始化 CAE 工作空间')
    projects = store.get('cae_projects', [])
    if any(p['id'].casefold() == project_id.strip().casefold() for p in projects):
        raise ValueError('项目编号已存在，请使用不同编号')
    entries = project_plan(project_id.strip(), client.strip(), name.strip(), keywords)
    library_id = store.get('cae_workspace_roots', {}).get(workspace)
    library = next((c for c in store.categories() if c['id'] == library_id), None)
    if not library:
        raise ValueError('项目库分类已被修改或删除，请检查工作空间')
    root, parent = Path(library['destination']), library['id']
    project = dict(id=project_id.strip(), client=client.strip(), name=name.strip(), workspace=workspace)
    ids = apply_plan(store, root, entries, project_id=project['id'], parent=parent,
                     extra_settings={'cae_projects': projects + [project]})
    store.event('CAE 项目', '已创建项目与基准工况：' + project['id'])
    return ids


def allowed_category(store, cid):
    policies = store.get('category_policies', {})
    if not policies.get(cid, {}).get('allow_files', True):
        return False
    cats = {c['id']: c for c in store.categories()}
    seen = set()
    while cid in cats and cid not in seen:
        seen.add(cid)
        if policies.get(cid, {}).get('protected', False):
            return False
        cid = cats[cid]['parent']
    return True


def protected_source(store, path):
    if not store.get('cae_mode', False):
        return False
    p = Path(path)
    if p.suffix.lower() in SOLVER_EXTENSIONS:
        return True
    sources = [Path(s).resolve() for s in store.get('sources', [])]
    for folder in p.resolve().parents:
        if not any(folder.is_relative_to(s) for s in sources):
            break
        if (folder / '.fileatlas-case.json').is_file():
            return True
        # A nested folder containing a native solver input is treated as a unit.
        if folder not in sources:
            try:
                if any(x.is_file() and x.suffix.lower() in SOLVER_EXTENSIONS for x in folder.iterdir()):
                    return True
            except OSError:
                return True
    return False


def review_reason(store, path, cid):
    if not store.get('cae_mode', False):
        return ''
    text = str(path).casefold()
    matches = {p['id'] for p in store.get('cae_projects', [])
               if re.search(r'(?<![a-z0-9])' + re.escape(p['id'].casefold()) + r'(?![a-z0-9-])', text)}
    project = store.get('category_policies', {}).get(cid, {}).get('project_id')
    if project and matches != {project}:
        return '项目编号不明确、存在多个编号或与推荐分类不一致，必须人工审核。'
    if matches and not project:
        return '文件含项目编号，但推荐的是公共分类，必须人工审核。'
    return ''
