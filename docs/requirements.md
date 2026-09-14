# Requirements Document

## Introduction

本文档定义独立的多市场量化研究平台首期版本。平台面向单一研究用户，以 A 股、港股、美股、ETF 和开放式基金为研究对象，统一处理资产身份、交易日历、时区、币种、汇率、公司行动、行情、点时基本面、因子、横截面、组合、回测、风险、绩效归因和实验复现。

首期版本以日频和低频研究为边界，优先保证跨市场语义明确、数据来源可追溯、市场微结构可配置、点时数据无前视、组合约束可验证以及研究结果可重放。首期版本不连接券商，不生成或提交真实订单，不处理超高频数据、复杂衍生品、分布式大数据计算或多租户 SaaS。

本文档是 `multi-market-quant-platform` 的独立需求基线。其他项目的需求、设计、数据和运行状态不构成本平台的隐式依赖。

## Glossary

- **多市场量化平台（Multi_Market_Quant_Platform）**：本规格定义的独立量化研究软件整体。
- **首期版本（MVP）**：由“首期范围”和本文件验收标准共同限定的第一个可用版本。
- **研究用户（Research_User）**：在本地研究环境中配置数据、运行研究并查看结果的唯一用户。
- **本地研究环境（Local_Research_Environment）**：由研究用户控制的设备、文件系统、数据库和进程边界。
- **研究工作区（Research_Workspace）**：保存本平台配置、数据引用、研究定义和研究产物的独立本地目录。
- **资产（Asset）**：可由平台标识、查询或纳入研究的金融资产。
- **股票（Equity）**：在受支持证券市场上市的普通股或等价权益证券。
- **交易所交易基金（ETF）**：在受支持证券市场挂牌交易的基金。
- **开放式基金（Open_End_Fund）**：按基金份额净值申购或赎回且不依赖盘中撮合的基金。
- **A 股市场（A_Share_Market）**：以上海证券交易所或深圳证券交易所上市人民币股票和 ETF 为首期范围的市场集合。
- **港股市场（Hong_Kong_Market）**：以香港联合交易所上市股票和 ETF 为首期范围的市场。
- **美股市场（United_States_Market）**：以纽约证券交易所、纳斯达克证券交易所或 NYSE American 上市股票和 ETF 为首期范围的市场集合。
- **市场（Market）**：A_Share_Market、Hong_Kong_Market 或 United_States_Market 之一。
- **规范资产标识（Canonical_Asset_ID）**：由平台分配且不依赖单一数据供应商代码的稳定资产标识。
- **资产主数据（Asset_Master）**：包含规范资产标识、资产类型、市场、交易所、名称、交易币种、生命周期和有效期的数据。
- **供应商资产映射（Provider_Asset_Mapping）**：供应商代码与规范资产标识之间带有效起止日期的对应关系。
- **资产生命周期状态（Asset_Lifecycle_Status）**：待上市、活跃、暂停上市、已退市、已到期或未知之一。
- **数据供应商（Data_Provider）**：依据自身许可向研究用户提供资产、行情、基金净值、基本面、公司行动、日历或汇率数据的外部服务。
- **供应商适配器（Provider_Adapter）**：把数据供应商的认证、能力、请求、响应和错误转换为平台统一契约的组件。
- **适配器契约（Adapter_Contract）**：供应商适配器必须实现的版本化输入、输出、能力发现、来源和错误约定。
- **合规档案（Compliance_Profile）**：记录数据供应商、账户类型、许可用途、保存许可、导出许可和确认时间的版本化配置。
- **日线行情（Daily_Bar）**：包含交易日期、开盘价、最高价、最低价、收盘价、成交量和成交额的日频记录。
- **基金净值（Fund_NAV）**：包含估值日期、单位净值以及供应商提供时的累计净值的开放式基金记录。
- **基本面事实（Fundamental_Fact）**：带度量名称、数值、单位、币种、报告期、公告时间、供应商可用时间和修订版本的公司或基金事实。
- **点时数据（Point_In_Time_Data）**：仅从供应商可用时间开始对研究可见的数据版本。
- **供应商可用时间（Provider_Available_At）**：数据供应商声明或平台记录的某一数据版本首次可供获取的带时区时刻。
- **公司行动（Corporate_Action）**：现金分红、股票分拆、合股、送股、配股、供股、合并、分拆或其他改变持仓或价格可比性的事件。
- **原始值（Raw_Value）**：数据供应商返回且未经过平台变换的字段值。
- **复权因子（Adjustment_Factor）**：带来源、适用日期和版本且用于生成可比价格序列的参数。
- **复权模式（Adjustment_Mode）**：不复权、前复权或后复权之一。
- **交易日历（Trading_Calendar）**：按市场、交易所、IANA 时区和版本记录交易日及交易时段的日期集合。
- **估值日历（Valuation_Calendar）**：记录开放式基金预期公布净值日期、适用时区和版本的日期集合。
- **市场时区（Market_Timezone）**：A 股使用 `Asia/Shanghai`、港股使用 `Asia/Hong_Kong`、美股使用 `America/New_York` 的 IANA 时区语义。
- **交易会话（Trading_Session）**：交易日历中带本地开始时间、本地结束时间和会话类型的交易时段。
- **常规交易会话（Regular_Trading_Session）**：市场主要连续交易或常规撮合时段；首期回测不使用盘前和盘后会话。
- **市场规则档案（Market_Rule_Profile）**：按市场、交易所、资产类型和有效期记录交易单位、价格最小变动、价格限制、卖出可用规则、结算周期和允许会话的版本化规则集合。
- **交易单位（Trading_Lot）**：市场规则档案要求的一次模拟交易数量增量。
- **价格最小变动（Tick_Size）**：市场规则档案对给定价格区间规定的最小报价增量。
- **价格限制（Price_Limit）**：适用市场规则档案规定的静态涨跌幅限制或供应商提供的动态价格带状态。
- **停牌状态（Halt_Status）**：资产在指定交易会话可交易、停牌、价格受限、已退市或未知的状态。
- **卖出可用日期（Sell_Available_Date）**：新买入数量首次可用于模拟卖出的市场日期。
- **结算日期（Settlement_Date）**：模拟交易现金和证券完成结算的市场日期。
- **交易币种（Trading_Currency）**：资产交易或基金计价所使用的 ISO 4217 币种。
- **基础币种（Base_Currency）**：研究、组合和报告用于汇总价值的单一 ISO 4217 币种。
- **外汇汇率（FX_Rate）**：带货币对、定价日期、方向、来源和版本的换算比率。
- **外汇策略（FX_Policy）**：规定基础币种、汇率日期选择、缺失汇率处理和外汇收益分解的研究配置。
- **规范化数据集（Canonical_Dataset）**：按照统一字段、类型、单位、规范资产标识、日期、时区和币种语义保存的数据集合。
- **数据版本（Data_Version）**：对规范化数据集一次不可变变化的标识。
- **数据快照（Data_Snapshot）**：以不可变标识引用资产、行情、净值、基本面、公司行动、日历、市场规则、汇率和质量结果版本的集合。
- **数据来源记录（Data_Provenance）**：记录供应商、供应商代码、请求参数、检索时间、源版本和合规档案版本的信息。
- **数据质量状态（Data_Quality_Status）**：有效、警告或拒绝之一。
- **数据质量报告（Data_Quality_Report）**：包含检查范围、规则版本、问题证据、数据质量状态和生成时间的报告。
- **数据摄取服务（Data_Ingestion_Service）**：获取、解析、规范化、版本化并发布数据的组件。
- **资产登记服务（Asset_Registry）**：维护资产主数据、供应商资产映射和生命周期的组件。
- **日历服务（Calendar_Service）**：维护交易日历、估值日历和时间语义的组件。
- **公司行动服务（Corporate_Action_Service）**：维护公司行动、复权因子和持仓变更语义的组件。
- **外汇服务（FX_Service）**：维护汇率并执行币种换算的组件。
- **数据质量服务（Data_Quality_Service）**：执行质量规则、分配质量状态并生成质量报告的组件。
- **因子定义（Factor_Definition）**：包含因子标识、输入字段、观察窗口、变换、缺失值规则、极值处理、标准化、中性化和版本的机器可读定义。
- **因子值（Factor_Value）**：某规范资产在某因子日期按一个因子定义版本计算的数值或明确缺失结果。
- **因子研究服务（Factor_Research_Service）**：计算因子值、形成横截面并评估因子统计特征的组件。
- **横截面（Cross_Section）**：在一个因子日期按点时规则可见且满足资产范围条件的资产集合。
- **资产范围（Universe）**：由市场、资产类型、生命周期、流动性和显式筛选条件定义的资产集合。
- **点时资产范围（Point_In_Time_Universe）**：保存每个日期有效成员资格及成员资格来源版本的资产范围。
- **中性化（Neutralization）**：从因子值中移除指定行业、市场、币种或规模暴露的横截面变换。
- **信息系数（Information_Coefficient）**：同一横截面中因子值与指定未来收益之间的 Pearson 或 Spearman 相关系数。
- **分组收益（Quantile_Return）**：按因子值排序分组后各组在指定持有期的资产收益聚合值。
- **前视偏差（Lookahead_Bias）**：研究使用在研究决策时刻尚不可见的数据所产生的偏差。
- **幸存者偏差（Survivorship_Bias）**：研究资产范围遗漏当时有效但后来退出资产所产生的偏差。
- **组合定义（Portfolio_Definition）**：包含基础币种、资产范围、基准、目标权重生成方法和约束的版本化配置。
- **目标权重（Target_Weight）**：组合定义为指定再平衡日期分配给资产或现金的基础币种价值比例。
- **组合约束（Portfolio_Constraint）**：资产权重、市场权重、币种权重、行业权重、现金权重、换手率或持仓数量的可验证限制。
- **组合构建服务（Portfolio_Construction_Service）**：根据预期信号和组合约束生成目标权重的组件。
- **基准（Benchmark）**：用于比较收益、风险和归因的点时资产范围及权重序列。
- **策略（Strategy）**：使用日频或更低频点时输入生成组合目标权重的版本化研究逻辑。
- **回测（Backtest）**：在历史数据和显式市场假设下模拟策略组合变化的研究运行。
- **回测引擎（Backtest_Engine）**：推进多市场日期、生成再平衡、模拟成交、处理公司行动、记账和估值的组件。
- **模拟交易（Simulated_Trade）**：回测引擎生成且不发送到任何交易场所的研究记录。
- **交易成本模型（Transaction_Cost_Model）**：按市场记录佣金、税费、平台费用、滑点和最低费用的版本化回测假设。
- **风险模型（Risk_Model）**：包含收益窗口、协方差估计、因子暴露和特异风险版本的机器可读配置。
- **风险分析服务（Risk_Analytics_Service）**：计算组合波动、回撤、跟踪误差、贝塔、风险贡献和集中度的组件。
- **绩效归因服务（Performance_Attribution_Service）**：把组合收益分解为资产贡献、市场或行业配置、证券选择和外汇效果的组件。
- **研究运行（Research_Run）**：使用确定数据快照、研究逻辑、参数和环境执行的一次因子、组合、回测、风险或归因实验。
- **实验清单（Experiment_Manifest）**：记录研究运行、数据快照、资产范围、日期范围、基础币种、外汇策略、供应商、日历、市场规则、复权、质量规则、因子、组合、策略、成本、风险模型、参数、随机种子、代码版本和依赖环境的信息。
- **实验运行器（Experiment_Runner）**：创建研究运行、保存实验清单、发布结果并重放研究运行的组件。
- **研究接口（Research_Interface）**：供本地页面、命令行或本地 Python 脚本只读查询数据并提交研究运行的统一入口。
- **凭据（Credential）**：访问数据供应商所需的 API 密钥、令牌、密码或等价秘密。
- **凭据管理器（Credential_Manager）**：在本地保存、读取、遮蔽和删除凭据的组件。
- **敏感信息遮蔽（Secret_Redaction）**：以固定占位符替换凭据及可恢复凭据的表示。
- **备份清单（Backup_Manifest）**：记录备份包含项、数据版本、记录数、内容校验和和模式版本的文件。

## 首期范围

首期版本包含：

- 单一研究用户、单一本地研究环境和独立研究工作区。
- A 股、港股、美股的股票与 ETF，以及以供应商覆盖为准的开放式基金。
- 日线行情、基金日频净值、日频外汇汇率、公司行动和低频点时基本面。
- 稳定规范资产标识、有效期供应商映射、生命周期和点时资产范围。
- A 股、港股、美股的版本化交易日历、IANA 时区和市场规则档案。
- 显式基础币种、跨币种估值、外汇缺失策略和外汇收益分解。
- 可配置供应商适配器、数据来源、许可约束、增量摄取和数据质量检查。
- 版本化因子定义、横截面变换、信息系数、分组收益和换手分析。
- 多市场多头组合构建、约束验证、日频再平衡回测和交易成本。
- 风险指标、资产贡献、市场或行业配置、证券选择和外汇效果归因。
- 不可变数据快照、实验清单、确定性重放、本地只读研究接口、备份与恢复。

## 未来扩展（不属于首期验收范围）

以下能力不构成首期验收标准：

- 券商连接、模拟盘、实盘下单、订单路由、自动执行和生产组合再平衡。
- 分钟、逐笔、订单簿、超高频、低延迟事件处理和盘前盘后策略。
- 做空、融资融券、杠杆、期权、期货、掉期和其他复杂衍生品。
- A 股、港股、美股以外市场的内置市场规则实现。
- 复杂税务批次、跨境资本管制、基金申赎费用全模型和个人税务优化。
- 分布式对象存储、集群计算、流式湖仓、超大规模因子平台和自动机器学习。
- 多用户权限、机构审批、团队协作、多租户 SaaS、云托管和公开数据服务。
- 自定义不受信代码的操作系统级沙箱和第三方策略市场。

## Requirements

### Requirement 1: 独立本地研究边界

**User Story:** 作为研究用户，我希望平台作为独立本地研究项目运行，以便在不影响其他项目或连接交易系统的条件下开展量化研究。

#### Acceptance Criteria

1. THE Multi_Market_Quant_Platform SHALL store all platform configuration, data references, Experiment_Manifests, and research results for one Research_Workspace exclusively within that Research_Workspace.
2. THE Multi_Market_Quant_Platform SHALL bind each Research_Workspace to exactly one Research_User operating-system identity for state-changing operations.
3. WHEN the bound Research_User operating-system identity requests a state-changing operation, THE Multi_Market_Quant_Platform SHALL apply the complete operation to the selected Research_Workspace as one atomic state change.
4. IF an operating-system identity other than the bound Research_User operating-system identity requests a state-changing operation, THEN THE Multi_Market_Quant_Platform SHALL reject the complete operation, identify the identity mismatch, and preserve every Research_Workspace record unchanged.
5. THE Multi_Market_Quant_Platform SHALL expose zero operations that create, submit, modify, cancel, or route a real securities or fund order.
6. WHEN the Multi_Market_Quant_Platform presents a Backtest or portfolio result, THE Multi_Market_Quant_Platform SHALL mark the complete result as a research simulation that is neither investment advice nor an executable order.
7. IF the Research_User requests a capability listed under future extensions, THEN THE Multi_Market_Quant_Platform SHALL reject the complete request, identify the capability as outside the MVP, execute zero external market transactions, and preserve the Research_Workspace unchanged.
8. WHEN the Multi_Market_Quant_Platform creates a Research_Workspace, THE Multi_Market_Quant_Platform SHALL assign one workspace identifier and one storage location that are unequal to the identifiers and storage locations of every existing Research_Workspace.
9. WHEN the Multi_Market_Quant_Platform opens a Research_Workspace, THE Multi_Market_Quant_Platform SHALL associate the opened workspace with exactly one previously assigned workspace identifier and storage location.
10. IF a requested Research_Workspace identifier equals an existing identifier or a requested storage location equals, contains, or is contained by an existing Research_Workspace storage location, THEN THE Multi_Market_Quant_Platform SHALL reject the complete create or open operation, identify every conflict, and preserve every existing Research_Workspace unchanged.

### Requirement 2: 资产覆盖与规范身份

**User Story:** 作为研究用户，我希望跨供应商和市场稳定识别股票、ETF 与基金，以便合并数据时避免代码冲突和历史误配。

#### Acceptance Criteria

1. WHEN the Asset_Registry accepts an Asset record, THE Asset_Registry SHALL classify the Asset as exactly one of Equity, ETF, or Open_End_Fund.
2. WHEN the Asset_Registry accepts an Asset record whose Market, exchange, asset type, and exchange-local code combination has no registered Asset, THE Asset_Registry SHALL assign exactly one new Canonical_Asset_ID to that combination.
3. WHEN the Asset_Registry accepts an Asset record whose Market, exchange, asset type, and exchange-local code combination already has a registered Asset, THE Asset_Registry SHALL return the existing Canonical_Asset_ID and create zero additional Canonical_Asset_ID values.
4. IF two accepted Asset records differ in Market, exchange, asset type, or exchange-local code, THEN THE Asset_Registry SHALL associate the two Asset records with different Canonical_Asset_ID values.
5. WHEN an accepted Asset name, Asset_Lifecycle_Status, exchange, or Trading_Currency changes, THE Asset_Registry SHALL create exactly one new effective-dated Asset_Master version and preserve every preceding Asset_Master version unchanged.
6. WHEN the Asset_Registry receives an Asset record, THE Asset_Registry SHALL validate Market as A_Share_Market, Hong_Kong_Market, or United_States_Market; asset type as Equity, ETF, or Open_End_Fund; exchange and exchange-local code as non-empty values of at most 64 characters each; name as a non-empty value of at most 256 characters; Trading_Currency as one ISO 4217 currency; and Asset_Lifecycle_Status as one status defined in the Glossary.
7. IF an Asset record omits or violates any Asset validation rule, THEN THE Asset_Registry SHALL reject the complete Asset record, identify every omitted or invalid value, create zero Canonical_Asset_ID or Asset_Master versions, and preserve all registered Asset data unchanged.
8. WHEN the Asset_Registry accepts a Provider_Asset_Mapping, THE Asset_Registry SHALL store exactly one Data_Provider, one non-empty provider code of at most 128 characters, one Canonical_Asset_ID, one inclusive effective start date, and one inclusive effective end date.
9. IF a Provider_Asset_Mapping has an unknown Canonical_Asset_ID, an empty provider code, a provider code longer than 128 characters, an omitted effective date, or an effective end date earlier than the effective start date, THEN THE Asset_Registry SHALL reject the complete Provider_Asset_Mapping, identify every invalid value, and preserve all Provider_Asset_Mappings unchanged.
10. WHEN exactly one Provider_Asset_Mapping contains an observation date within the inclusive effective interval for a Data_Provider and provider code, THE Asset_Registry SHALL return the single associated Canonical_Asset_ID.
11. IF zero Provider_Asset_Mappings contain an observation date within the inclusive effective interval for a Data_Provider and provider code, THEN THE Asset_Registry SHALL return one unresolved-asset result containing the Data_Provider, provider code, and observation date and preserve all Asset data unchanged.
12. IF more than one Provider_Asset_Mapping contains an observation date within the inclusive effective interval for a Data_Provider and provider code, THEN THE Asset_Registry SHALL return one ambiguous-asset result containing every matching Canonical_Asset_ID and effective interval and preserve all Asset data unchanged.
13. WHEN the Research_User queries an Asset by Canonical_Asset_ID and historical date, THE Asset_Registry SHALL return the single Asset_Master version whose inclusive effective interval contains the historical date, including versions for delisted or terminated Assets.
14. THE Asset_Registry SHALL preserve every superseded, delisted, and terminated Asset_Master version as an immutable queryable historical record.

### Requirement 3: 数据供应商适配与合规

**User Story:** 作为研究用户，我希望可替换数据供应商并明确数据许可，以便按覆盖和授权条件获取多市场数据。

#### Acceptance Criteria

1. THE Provider_Adapter SHALL declare exactly one Adapter_Contract version.
2. THE Provider_Adapter SHALL declare authentication references, supported Markets, supported asset types, supported data categories, inclusive available date ranges, update frequencies, request limits, normalized response capability, Data_Provenance capability, and categorized error capability under the declared Adapter_Contract version.
3. WHEN the Research_User enables a Provider_Adapter, THE Multi_Market_Quant_Platform SHALL present the complete declared capability set and the declared Adapter_Contract version before sending the first provider request.
4. WHEN a Provider_Adapter omits a Market, asset-type, data-category, date-range, update-frequency, request-limit, normalized-response, Data_Provenance, or categorized-error capability value, THE Multi_Market_Quant_Platform SHALL present that capability value as unknown.
5. WHEN a Provider_Adapter declares a request limit, THE Provider_Adapter SHALL express the limit as an integer from 1 through 1000000 requests and a measurement period from 1 through 86400 seconds.
6. IF a Provider_Adapter declares an Adapter_Contract version that the Multi_Market_Quant_Platform does not support, THEN THE Multi_Market_Quant_Platform SHALL keep the Provider_Adapter disabled, identify the incompatible version, send zero requests through the Provider_Adapter, and preserve provider data unchanged.
7. WHEN the Research_User configures a Data_Provider for the first time, THE Multi_Market_Quant_Platform SHALL require exactly one valid Compliance_Profile version before sending the first provider request.
8. THE Multi_Market_Quant_Platform SHALL validate each Compliance_Profile version for one provider name, one account type, at least one permitted research purpose, one explicit retention permission per supported data category, one explicit export permission per supported data category, one confirmation timestamp with an explicit UTC offset, and one immutable version identifier.
9. IF a required Compliance_Profile value is absent or invalid, THEN THE Multi_Market_Quant_Platform SHALL reject the complete Compliance_Profile, identify every absent or invalid value, send zero provider requests, and preserve every existing Compliance_Profile version unchanged.
10. WHEN the Research_User changes a Compliance_Profile, THE Multi_Market_Quant_Platform SHALL create exactly one new immutable Compliance_Profile version and preserve every preceding version unchanged.
11. WHEN the Data_Ingestion_Service sends a provider request, THE Data_Ingestion_Service SHALL bind the request to exactly one Compliance_Profile version that is valid for the Data_Provider and request time.
12. IF the bound Compliance_Profile prohibits retention of a requested data category, THEN THE Data_Ingestion_Service SHALL persist zero Raw_Values, normalized observations, Data_Versions, or Data_Snapshots from the complete provider response and preserve every pre-existing persisted record unchanged.
13. IF the bound Compliance_Profile prohibits export of a requested data category, THEN THE Multi_Market_Quant_Platform SHALL produce zero export bytes, identify the bound Compliance_Profile version and prohibited data category, and preserve every pre-existing export and persisted record unchanged.
14. WHEN the Data_Ingestion_Service persists a provider observation, THE Data_Ingestion_Service SHALL associate the complete observation with exactly one Data_Provenance record and exactly one Compliance_Profile version.
15. IF a Data_Provider returns no complete response within 30 seconds after a request is sent, THEN THE Provider_Adapter SHALL return one timeout error containing the provider name, request category, retry eligibility, and provider correlation identifier when supplied and preserve all normalized and persisted data unchanged.
16. IF a Data_Provider rejects a request because of throttling or is unavailable before 30 seconds elapse, THEN THE Provider_Adapter SHALL return one categorized error containing the provider name, request category, retry eligibility, and provider correlation identifier when supplied and preserve all normalized and persisted data unchanged.

### Requirement 4: 多市场日历、时区与会话

**User Story:** 作为研究用户，我希望平台按各市场本地日历和时区解释数据，以便避免跨市场日期错位和美股夏令时错误。

#### Acceptance Criteria

1. WHEN the Calendar_Service accepts a Trading_Calendar version, THE Calendar_Service SHALL store exactly one Market, one exchange, one Market_Timezone, one inclusive effective interval, and one immutable version identifier for the complete version.
2. THE Calendar_Service SHALL use `Asia/Shanghai` for A_Share_Market, `Asia/Hong_Kong` for Hong_Kong_Market, and `America/New_York` for United_States_Market.
3. WHEN the Calendar_Service interprets a timestamp containing a UTC offset, THE Calendar_Service SHALL convert the timestamp to the Market_Timezone selected by Market and exchange before assigning exactly one market date.
4. WHEN the Calendar_Service interprets a United_States_Market timestamp containing a UTC offset, THE Calendar_Service SHALL apply the `America/New_York` daylight-saving or standard-time offset in effect at that timestamp.
5. IF a timestamp lacks a UTC offset or named IANA time zone, THEN THE Calendar_Service SHALL reject the complete date interpretation, identify the missing time-zone information, assign no market date, and preserve all calendar data unchanged.
6. WHEN the Calendar_Service accepts a Trading_Calendar market date, THE Calendar_Service SHALL classify the date as exactly one of closed, full trading day, or half-day and classify each of zero through eight Trading_Sessions as regular or non-regular.
7. WHEN the Calendar_Service accepts a Trading_Session, THE Calendar_Service SHALL store one local start time, one later local end time, and exactly one session type under the Trading_Calendar version.
8. WHEN a Trading_Calendar version contains a split trading day, THE Calendar_Service SHALL preserve every Trading_Session as a separate interval ordered by local start time.
9. WHEN the Calendar_Service accepts a Valuation_Calendar version, THE Calendar_Service SHALL store exactly one fund market, one named IANA time zone, one inclusive effective interval, and one immutable version identifier for the complete version.
10. WHEN exactly one calendar version contains an observation timestamp within the inclusive effective interval for the requested Market and exchange, THE Calendar_Service SHALL use that single calendar version for date interpretation.
11. IF zero or more than one calendar version contains an observation timestamp within the inclusive effective interval for the requested Market and exchange, THEN THE Calendar_Service SHALL reject the complete date interpretation, identify the missing or ambiguous calendar versions, assign no market date, and preserve all calendar data unchanged.
12. IF a Trading_Calendar or Valuation_Calendar version omits a required value, uses a non-IANA time zone, has an effective end before the effective start, contains more than eight Trading_Sessions on one date, contains a Trading_Session whose end is not later than its start, or contains overlapping Trading_Sessions, THEN THE Calendar_Service SHALL reject the complete calendar version, identify every invalid value, and preserve all accepted calendar versions unchanged.
13. WHEN the Research_User requests cross-Market alignment using one specified alignment date and one research decision timestamp, THE Calendar_Service SHALL return each included observation with exactly one unchanged source market date and exactly one specified alignment date.
14. IF a cross-Market alignment candidate has a Provider_Available_At later than the research decision timestamp, THEN THE Calendar_Service SHALL exclude the complete observation from the aligned input, record the point-in-time exclusion reason, and preserve the source observation unchanged.
15. IF a cross-Market alignment candidate has a Provider_Available_At equal to or earlier than the research decision timestamp, THEN THE Calendar_Service SHALL retain the observation subject to the requested Market, exchange, and alignment date.

### Requirement 5: 市场微结构规则

**User Story:** 作为研究用户，我希望回测显式应用 A 股、港股和美股的不同市场规则，以便避免使用统一但错误的成交假设。

#### Acceptance Criteria

1. WHEN the Backtest_Engine evaluates a Simulated_Trade, THE Backtest_Engine SHALL select exactly one Market_Rule_Profile version by Market, exchange, asset type, and simulated trade date.
2. THE Multi_Market_Quant_Platform SHALL require each Market_Rule_Profile version to define one positive integer Trading_Lot from 1 through 1000000000 units, one positive Tick_Size no greater than 1000000000 units of Trading_Currency, Price_Limit semantics, one Sell_Available_Date rule, one Settlement_Date rule, and from one through eight permitted Trading_Session types.
3. IF a Market_Rule_Profile omits a required rule, contains a Trading_Lot or Tick_Size outside the permitted range, or contains zero or more than eight permitted Trading_Session types, THEN THE Multi_Market_Quant_Platform SHALL reject the complete Market_Rule_Profile version, identify every invalid rule, and preserve every accepted Market_Rule_Profile version unchanged.
4. IF zero or more than one Market_Rule_Profile version matches a Simulated_Trade by Market, exchange, asset type, and simulated trade date, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, identify every missing or ambiguous lookup value, and preserve positions and cash unchanged for the complete trade request.
5. WHEN the Backtest_Engine simulates an A_Share_Market purchase, THE Backtest_Engine SHALL set the Sell_Available_Date to the first open A_Share_Market trading date after the purchase date.
6. WHEN the Backtest_Engine simulates a Hong_Kong_Market or United_States_Market purchase, THE Backtest_Engine SHALL set the Sell_Available_Date to the purchase date when the selected Market_Rule_Profile specifies same-day sell availability.
7. WHEN the Backtest_Engine validates a requested quantity, THE Backtest_Engine SHALL set the valid-lot quantity to the greatest integer multiple of Trading_Lot not exceeding the absolute requested quantity while preserving the requested trade side.
8. IF the valid-lot quantity is zero, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, record the invalid-lot reason, and preserve positions and cash unchanged for the complete trade request.
9. WHEN the Backtest_Engine validates a positive requested trade price, THE Backtest_Engine SHALL set the valid-tick price to the greatest integer multiple of Tick_Size not exceeding the requested trade price.
10. IF a requested trade price is not positive, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, record the invalid-price reason, and preserve positions and cash unchanged for the complete trade request.
11. IF an A_Share_Market Price_Limit blocks the requested trade side under the selected market-data version or Market_Rule_Profile version, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, record the Price_Limit reason and source version, and preserve positions and cash unchanged for the complete trade request.
12. IF a Hong_Kong_Market or United_States_Market provider-supplied price band blocks the requested trade side, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, record the price-band reason and source version, and preserve positions and cash unchanged for the complete trade request.
13. IF Halt_Status is suspended, delisted, or unknown for the requested Trading_Session, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, record the Halt_Status reason, and preserve positions and cash unchanged for the complete trade request.
14. IF a requested Simulated_Trade falls outside every Trading_Session type permitted by the selected Market_Rule_Profile, THEN THE Backtest_Engine SHALL defer the complete request to the first subsequent permitted Trading_Session and preserve positions and cash unchanged before that session.
15. IF no subsequent permitted Trading_Session exists within the effective interval of the selected Trading_Calendar and Market_Rule_Profile versions, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, record the unavailable-session reason, and preserve positions and cash unchanged for the complete trade request.
16. THE Backtest_Engine SHALL exclude United_States_Market pre-market and after-hours Trading_Sessions from MVP simulated execution.
17. IF a requested sell date is earlier than the Sell_Available_Date for any requested quantity, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, record the unavailable-quantity reason, and preserve positions and cash unchanged for the complete trade request.
18. WHEN the Backtest_Engine simulates a filled trade, THE Backtest_Engine SHALL record exactly one Sell_Available_Date and exactly one Settlement_Date calculated independently under the selected Market_Rule_Profile version.
19. WHILE a filled trade has not reached the Settlement_Date, THE Backtest_Engine SHALL classify the trade cash and securities as unsettled.
20. WHEN the Settlement_Date of a filled trade is reached, THE Backtest_Engine SHALL transfer the complete trade cash and securities from unsettled balances to settled balances exactly once.

### Requirement 6: 币种、汇率与跨市场估值

**User Story:** 作为研究用户，我希望以明确汇率把多币种资产汇总到基础币种，以便比较和管理跨市场组合。

#### Acceptance Criteria

1. THE Multi_Market_Quant_Platform SHALL require exactly one Base_Currency expressed as one ISO 4217 currency for each Portfolio_Definition, Backtest, risk report, and attribution report.
2. THE FX_Service SHALL store each FX_Rate as one immutable version containing exactly one source currency, one target currency different from the source currency, one rate date, one Decimal rate in the inclusive range `1e-12` through `1e12`, one Data_Provider, one retrieval time with explicit UTC offset, and one Data_Provenance record.
3. WHEN the FX_Service accepts a direct FX_Rate, THE FX_Service SHALL associate the FX_Rate with the Data_Provider, provider currency-pair representation, retrieval time, Data_Version, and Data_Provenance used to obtain the rate.
4. WHEN the FX_Service derives an inverse FX_Rate, THE FX_Service SHALL set the inverse rate to exactly one divided by the direct rate under Decimal arithmetic and retain the direct FX_Rate version as the derivation source.
5. WHEN an Asset value uses a Trading_Currency different from the Base_Currency, THE FX_Service SHALL convert the Asset value with exactly one FX_Rate version selected under the pinned FX_Policy.
6. WHEN an Asset value uses the Base_Currency, THE FX_Service SHALL use a conversion rate of exactly one without selecting an FX_Rate.
7. THE FX_Policy SHALL select exactly one rate-date convention from valuation-date rate or latest-prior-rate fallback.
8. WHEN the FX_Policy selects the valuation-date-rate convention, THE FX_Service SHALL select an FX_Rate whose rate date equals the valuation date.
9. WHEN the FX_Policy selects the latest-prior-rate fallback, THE FX_Service SHALL select the most recent available FX_Rate whose rate date is within the five applicable FX business dates ending on the valuation date.
10. IF no FX_Rate exists within the date set permitted by the pinned FX_Policy, THEN THE FX_Service SHALL return one unavailable conversion result identifying the source currency, target currency, valuation date, FX_Policy, and examined date set, with no converted value persisted.
11. WHEN the FX_Service returns a converted value, THE FX_Service SHALL return one conversion record containing the source value, source currency, selected FX_Rate, FX_Rate date, FX_Rate version, Data_Provenance, converted value, and Base_Currency.
12. WHEN the Performance_Attribution_Service calculates multi-currency attribution, THE Performance_Attribution_Service SHALL report local-asset return and FX effect as two separately valued components.
13. WHEN the FX_Service converts a positive Decimal value to another currency and converts the result back with the exact inverse of the same FX_Rate version, THE FX_Service SHALL reproduce the source value within relative error `abs(reproduced - source) / source <= 1e-12`.

### Requirement 7: 行情、净值与点时基本面摄取

**User Story:** 作为研究用户，我希望摄取一致且无前视的行情、基金净值和基本面，以便构建跨资产研究输入。

#### Acceptance Criteria

1. WHEN a Data_Provider supplies a Daily_Bar for a date classified as open by exactly one applicable Trading_Calendar version, THE Data_Ingestion_Service SHALL normalize the complete Daily_Bar as one atomic observation.
2. IF zero or more than one applicable Trading_Calendar version classifies a supplied Daily_Bar date, THEN THE Data_Ingestion_Service SHALL reject the complete Daily_Bar and persist no part of the observation.
3. WHEN the Data_Ingestion_Service validates a Daily_Bar, THE Data_Ingestion_Service SHALL accept each open, high, low, and close value only within the inclusive Decimal range `0.00000001` through `999999999999.99999999`.
4. WHEN the Data_Ingestion_Service validates a Daily_Bar, THE Data_Ingestion_Service SHALL accept volume and turnover only within the inclusive Decimal range `0` through `999999999999999999.99999999`.
5. WHEN the Data_Ingestion_Service validates a Daily_Bar, THE Data_Ingestion_Service SHALL require `high >= max(open, low, close)` and `low <= min(open, high, close)`.
6. WHEN a Data_Provider supplies a Fund_NAV for a date present in exactly one applicable Valuation_Calendar version, THE Data_Ingestion_Service SHALL accept unit net asset value only within the inclusive Decimal range `0.00000001` through `999999999999.99999999`.
7. WHEN a Data_Provider supplies cumulative net asset value, THE Data_Ingestion_Service SHALL accept cumulative net asset value only within the inclusive Decimal range `0.00000001` through `999999999999.99999999` and no lower than unit net asset value for the same Canonical_Asset_ID and valuation date.
8. THE Data_Ingestion_Service SHALL store each Fundamental_Fact as one immutable revision containing a metric name of 1 through 128 Unicode characters, one Decimal value in the inclusive range `-1e24` through `1e24`, a unit of 1 through 32 Unicode characters, exactly one ISO 4217 currency for currency-denominated metrics, one reporting period, one announcement time with explicit UTC offset, one Provider_Available_At with explicit UTC offset, one Data_Provider, and one revision version.
9. WHEN a Data_Provider supplies a revised Fundamental_Fact, THE Data_Ingestion_Service SHALL create exactly one immutable successor revision linked to the immediately preceding revision for the same Canonical_Asset_ID, metric name, and reporting period.
10. WHEN a research decision timestamp precedes a Fundamental_Fact Provider_Available_At, THE Multi_Market_Quant_Platform SHALL exclude that Fundamental_Fact revision from the research input and record the revision version and exclusion reason.
11. WHEN one or more Fundamental_Fact revisions have Provider_Available_At no later than a research decision timestamp, THE Multi_Market_Quant_Platform SHALL select the single revision with the latest Provider_Available_At and highest successor position among revisions tied at that timestamp.
12. IF a supplied Daily_Bar, Fund_NAV, or Fundamental_Fact has an absent required field or violates a numeric, calendar, currency, unit, timestamp, or field-length rule, THEN THE Data_Ingestion_Service SHALL atomically reject the complete observation, identify every violated rule, and preserve the current Canonical_Dataset unchanged.
13. THE Data_Ingestion_Service SHALL maintain at most one current Daily_Bar for each Canonical_Asset_ID and trading date.
14. THE Data_Ingestion_Service SHALL maintain at most one current Fund_NAV for each Canonical_Asset_ID and valuation date.
15. WHEN the Research_User requests an incremental update, THE Data_Ingestion_Service SHALL request exactly the maximal non-overlapping contiguous segments formed from expected dates absent from the selected Data_Version.
16. WHEN a normalized observation is byte-for-byte equal under the Canonical_Dataset field ordering to the current observation for the same logical key, THE Data_Ingestion_Service SHALL reuse the current Data_Version identifier without creating a successor version.
17. WHEN a normalized observation differs in at least one Canonical_Dataset field from the current observation for the same logical key, THE Data_Ingestion_Service SHALL create exactly one immutable successor Data_Version linked only to the immediately preceding Data_Version.

### Requirement 8: 公司行动与复权

**User Story:** 作为研究用户，我希望公司行动、价格复权和持仓变化具有统一且可追溯的语义，以便正确计算收益和组合价值。

#### Acceptance Criteria

1. THE Corporate_Action_Service SHALL store each Corporate_Action as one immutable version containing Canonical_Asset_ID, action type, announcement date, ex-date, record date or an explicit not-supplied state, payment or effective date, terms, Data_Provenance, and version identifier.
2. THE Corporate_Action_Service SHALL preserve every ingested Raw_Value price byte-for-byte unchanged across all Adjustment_Mode selections, Adjustment_Factor versions, and Corporate_Action revisions.
3. WHEN the Research_User requests an Equity or ETF price series, THE Corporate_Action_Service SHALL require exactly one Adjustment_Mode selected from unadjusted, forward-adjusted, or backward-adjusted.
4. IF an Equity or ETF price-series request specifies zero Adjustment_Modes or more than one Adjustment_Mode, THEN THE Corporate_Action_Service SHALL reject the complete request and persist no adjusted series.
5. WHEN the Research_User selects unadjusted Adjustment_Mode, THE Corporate_Action_Service SHALL return the Raw_Value price for every returned observation date.
6. WHEN the Research_User selects forward-adjusted or backward-adjusted Adjustment_Mode, THE Corporate_Action_Service SHALL use exactly one pinned Adjustment_Factor series containing one factor for every returned observation date.
7. IF any required Adjustment_Factor is absent, non-numeric, or outside the inclusive Decimal range `0.000000000001` through `1000000000000`, THEN THE Corporate_Action_Service SHALL reject the complete adjusted series, identify every invalid or absent factor date, and publish no adjusted value.
8. WHEN the Corporate_Action_Service returns an adjusted series, THE Corporate_Action_Service SHALL associate the series with Adjustment_Mode, Adjustment_Factor source, Adjustment_Factor version, factor anchor date, and Data_Provenance.
9. WHEN a Backtest first processes a pinned stock split, consolidation, stock distribution, or rights event for a held Asset, THE Backtest_Engine SHALL apply the event terms exactly once to simulated position quantity and cost basis.
10. WHEN a Backtest first processes a pinned cash distribution for a held Asset, THE Backtest_Engine SHALL credit the distribution exactly once on the pinned payment date under the pinned withholding assumption.
11. IF a Backtest encounters a Corporate_Action event identifier already applied to the same simulated position, THEN THE Backtest_Engine SHALL leave position quantity, cost basis, and cash unchanged for that event.
12. IF more than one active Corporate_Action version exists for the same Canonical_Asset_ID, action type, and effective date, THEN THE Corporate_Action_Service SHALL reject the complete affected price series, identify every conflicting version, and preserve every previously published series unchanged.
13. THE Multi_Market_Quant_Platform SHALL use a cumulative net asset value for an Open_End_Fund only when the cumulative net asset value is supplied by the Data_Provider.
14. IF a Data_Provider supplies no cumulative net asset value for an Open_End_Fund observation, THEN THE Multi_Market_Quant_Platform SHALL return an explicit unavailable cumulative-net-asset-value result without deriving or persisting a substitute value.

### Requirement 9: 数据质量、版本和缺口可见性

**User Story:** 作为研究用户，我希望平台量化并展示数据问题，以便在因子、组合和回测前判断数据适用性。

#### Acceptance Criteria

1. THE Data_Quality_Service SHALL execute exactly the pinned versions of all applicable rules in the finite rule categories uniqueness, required fields, numeric ranges, date validity, currency consistency, unit consistency, lifecycle consistency, mapping resolution, and provider timestamp order.
2. IF a quality rule fails, THEN THE Data_Quality_Service SHALL create one immutable issue record containing the rule identifier, rule version, severity, Canonical_Asset_ID or an explicit unavailable state, observation date, field, observed value or an explicit absent state, expected condition, unavailable dependency or an explicit none state, and evidence sufficient to reproduce the comparison.
3. WHEN all applicable quality rules complete, THE Data_Quality_Service SHALL assign exactly one Data_Quality_Status equal to the greatest applicable severity under the total order valid less than warning less than rejected.
4. WHEN a Daily_Bar is absent on a date classified as closed by exactly one applicable Trading_Calendar version, THE Data_Quality_Service SHALL assign the missing-reason code expected-calendar-gap.
5. WHEN a Daily_Bar is absent on an open market date with suspended Halt_Status, THE Data_Quality_Service SHALL assign the missing-reason code suspended-trading-gap.
6. WHEN a Daily_Bar is absent on an open market date with unknown or absent Halt_Status, THE Data_Quality_Service SHALL assign the missing-reason code unresolved-market-data-gap.
7. WHEN a Fund_NAV is absent on an expected Valuation_Calendar date, THE Data_Quality_Service SHALL assign the missing-reason code delayed-or-missing-valuation.
8. WHEN a Fundamental_Fact announcement time is later than Provider_Available_At, THE Data_Quality_Service SHALL assign rejected Data_Quality_Status to that immutable revision.
9. WHEN quality checks complete, THE Data_Quality_Service SHALL generate one Data_Quality_Report containing the checked scope, rule-set version, complete issue-record collection, counts for valid, warning, and rejected statuses, and generation time with explicit UTC offset.
10. WHEN the Multi_Market_Quant_Platform returns a time series with a missing expected observation, THE Multi_Market_Quant_Platform SHALL preserve the expected date with exactly one missing-reason code selected from expected-calendar-gap, suspended-trading-gap, unresolved-market-data-gap, or delayed-or-missing-valuation.
11. IF more than one missing-reason condition applies to the same expected observation, THEN THE Data_Quality_Service SHALL select exactly one code under the precedence suspended-trading-gap, delayed-or-missing-valuation, unresolved-market-data-gap, expected-calendar-gap.
12. IF a Data_Snapshot selects at least one rejected observation and lacks Research_User confirmation bound to the exact Data_Snapshot identifier and complete rejected-observation version set, THEN THE Experiment_Runner SHALL reject Research_Run creation and preserve all Research_Run records unchanged.
13. WHEN the Research_User confirms use of rejected observations, THE Experiment_Runner SHALL bind the confirmation to exactly one Data_Snapshot identifier and the complete immutable set of rejected observation versions selected by that Data_Snapshot.
14. WHEN the Data_Ingestion_Service publishes a Data_Version, THE Data_Ingestion_Service SHALL preserve every field and logical-key association of every prior Data_Version unchanged.
15. IF publication of a successor Data_Version fails, THEN THE Data_Ingestion_Service SHALL keep the current Data_Version identifier and every prior Data_Version unchanged.

### Requirement 10: 点时资产范围与偏差控制

**User Story:** 作为研究用户，我希望按历史时点构建资产范围，以便降低幸存者偏差和前视偏差。

#### Acceptance Criteria

1. THE Multi_Market_Quant_Platform SHALL store each Point_In_Time_Universe membership as one immutable record containing Canonical_Asset_ID, one inclusive effective start date, one inclusive effective end date, membership source, source version, and Universe version.
2. WHEN the Factor_Research_Service builds a Cross_Section for a factor date, THE Factor_Research_Service SHALL include exactly the Assets with one effective Point_In_Time_Universe membership on that factor date.
3. WHEN the Portfolio_Construction_Service builds Target_Weights for a rebalance date, THE Portfolio_Construction_Service SHALL include exactly the Assets with one effective Point_In_Time_Universe membership on that rebalance date.
4. IF zero or more than one membership record applies to the same Canonical_Asset_ID and research date within one Universe version, THEN THE Multi_Market_Quant_Platform SHALL exclude that Asset and record every absent or overlapping membership interval as exclusion evidence.
5. WHEN a Universe applies lifecycle filtering, THE Multi_Market_Quant_Platform SHALL evaluate only the Asset_Master version whose effective interval contains the research date.
6. WHEN a Universe applies liquidity filtering, THE Multi_Market_Quant_Platform SHALL evaluate only liquidity observations whose Provider_Available_At is no later than the research decision timestamp.
7. IF historical membership data is incomplete for at least one requested date, THEN THE Multi_Market_Quant_Platform SHALL attach a Survivorship_Bias warning containing every maximal contiguous incomplete date range, affected Universe version, and missing membership source.
8. IF an input value has Provider_Available_At later than the research decision timestamp, THEN THE Multi_Market_Quant_Platform SHALL exclude the input and create one Lookahead_Bias prevention record containing Canonical_Asset_ID, input version, Provider_Available_At, decision timestamp, and exclusion reason.
9. WHEN the Multi_Market_Quant_Platform excludes an Asset from a Cross_Section, THE Multi_Market_Quant_Platform SHALL retain one exclusion-evidence record containing Canonical_Asset_ID, factor date, decision timestamp, evaluated membership version, and exactly one exclusion reason.
10. WHEN the Multi_Market_Quant_Platform returns a Cross_Section, THE Multi_Market_Quant_Platform SHALL include factor date, decision timestamp, Universe version, member count as a non-negative integer, exclusion counts by reason as non-negative integers, Survivorship_Bias warnings, and Lookahead_Bias prevention-record count.
11. IF a historical lifecycle, liquidity, membership-source, or Provider_Available_At value required by a Universe rule is unavailable, THEN THE Multi_Market_Quant_Platform SHALL exclude the affected Asset, identify every unavailable input category, and preserve the Point_In_Time_Universe unchanged.

### Requirement 11: 因子定义与计算

**User Story:** 作为研究用户，我希望以版本化定义计算价格、基本面和混合因子，以便复用并解释每次因子实验。

#### Acceptance Criteria

1. THE Factor_Research_Service SHALL publish exactly one versioned transformation specification that defines each supported transformation name, input count, parameter bounds, minimum observation count, output-unit rule, and valid predecessor transformation types.
2. THE Factor_Research_Service SHALL require each Factor_Definition to contain exactly one unique factor identifier, one Data_Snapshot schema version, between 1 and 64 input fields, one integer observation window from 1 through 2520 periods, between 0 and 32 transformations in execution order, one missing-value rule, one extreme-value rule, one standardization rule, one Neutralization rule, one transformation-specification version, and one immutable Factor_Definition version.
3. WHEN the Research_User creates a Factor_Definition, THE Factor_Research_Service SHALL validate every input field against the selected Data_Snapshot schema and every transformation against the selected transformation specification.
4. IF a Factor_Definition violates a field-count bound, observation-window bound, transformation-count bound, transformation parameter bound, transformation ordering rule, or input-field reference, THEN THE Factor_Research_Service SHALL reject the complete Factor_Definition, identify every violated rule, persist no Factor_Definition version, and preserve all existing Factor_Definition versions unchanged.
5. WHEN the Factor_Research_Service calculates a Factor_Value for a factor decision timestamp, THE Factor_Research_Service SHALL use only Point_In_Time_Data visible at or before that factor decision timestamp.
6. IF a required Data_Snapshot, Point_In_Time_Universe version, input-field version, exposure version, or Trading_Calendar version is unavailable or ambiguous, THEN THE Factor_Research_Service SHALL return an undefined-factor result identifying every unavailable or ambiguous dependency, persist no Factor_Values for the calculation, and preserve all previously persisted Factor_Values unchanged.
7. WHEN a Factor_Definition specifies missing-value exclusion and an Asset has fewer than the required number of non-missing Point_In_Time_Data observations, THE Factor_Research_Service SHALL return exactly one missing Factor_Value for the Asset containing the required observation count, available observation count, and missing-input reason.
8. WHEN a Factor_Definition specifies winsorization with `0 <= q_lower < q_upper <= 1` over `n >= 1` non-missing Cross_Section values sorted as `x_(1) <= ... <= x_(n)`, THE Factor_Research_Service SHALL produce each winsorized value as `min(max(x, x_(floor(q_lower * (n - 1)) + 1)), x_(floor(q_upper * (n - 1)) + 1))`.
9. IF a Factor_Definition specifies winsorization with `q_lower < 0`, `q_upper > 1`, or `q_lower >= q_upper`, THEN THE Factor_Research_Service SHALL reject the complete Factor_Definition, identify every invalid quantile parameter, persist no Factor_Definition version, and preserve all existing Factor_Definition versions unchanged.
10. WHEN a Factor_Definition specifies z-score standardization for `n >= 2` non-missing values with `μ = (1 / n) * Σx_i` and positive population dispersion `σ = sqrt((1 / n) * Σ(x_i - μ)^2)`, THE Factor_Research_Service SHALL produce each standardized value within an absolute Decimal error of `1e-12` from `(x_i - μ) / σ`.
11. IF z-score standardization receives fewer than two non-missing values or population dispersion `σ = 0`, THEN THE Factor_Research_Service SHALL return one undefined-factor result for the Cross_Section, persist no numeric standardized Factor_Values for the Cross_Section, and preserve all previously persisted Factor_Values unchanged.
12. WHEN a Factor_Definition specifies Neutralization, THE Factor_Research_Service SHALL calculate Neutralization using exactly the exposure fields, exposure versions, and transformation order recorded in that Factor_Definition version.
13. WHEN the Factor_Research_Service persists a Factor_Value, THE Factor_Research_Service SHALL associate the Factor_Value with exactly one Factor_Definition version, Data_Snapshot identifier, Point_In_Time_Universe version, factor date, decision timestamp, and Data_Quality_Status.
14. WHEN the same Factor_Definition version, Data_Snapshot identifier, Point_In_Time_Universe version, factor date, and decision timestamp are evaluated more than once, THE Factor_Research_Service SHALL reproduce every missing or undefined status exactly and every numeric Factor_Value within `abs(recomputed - original) <= 1e-12 * max(1, abs(original))`.

### Requirement 12: 横截面因子评估

**User Story:** 作为研究用户，我希望评估因子的排序能力、分组收益和稳定性，以便判断因子是否值得用于组合构建。

#### Acceptance Criteria

1. WHEN an aligned set `S` contains `n >= 2` Assets with non-missing Factor_Values `x_i` and future returns `y_i`, THE Factor_Research_Service SHALL calculate Pearson Information_Coefficient as `Σ((x_i - mean(x)) * (y_i - mean(y))) / sqrt(Σ(x_i - mean(x))^2 * Σ(y_i - mean(y))^2)` over exactly the Assets in `S`.
2. WHEN an aligned set contains `n >= 2` Assets with at least two distinct non-missing Factor_Values and at least two distinct future returns, THE Factor_Research_Service SHALL calculate Spearman Information_Coefficient by assigning the average occupied rank to every tied value and applying the Pearson Information_Coefficient formula to the two rank vectors.
3. IF an Information_Coefficient input has fewer than two aligned non-missing pairs or zero dispersion, THEN THE Factor_Research_Service SHALL return an undefined-information-coefficient result identifying the invalid input and aligned-pair count and persist no numeric Information_Coefficient for that Cross_Section.
4. WHEN the Research_User selects an integer quantile count `Q` from 2 through 20 and the Cross_Section contains `n >= Q` distinct non-missing Factor_Values, THE Factor_Research_Service SHALL order Assets by ascending Factor_Value with ties ordered by ascending Canonical_Asset_ID and assign rank `r` to group `min(Q, floor((r - 1) * Q / n) + 1)`.
5. IF the requested quantile count is outside 2 through 20 or exceeds the count of distinct non-missing Factor_Values, THEN THE Factor_Research_Service SHALL return an invalid-quantile result containing the requested count and distinct-value count, persist no Quantile_Return for the Cross_Section, and preserve all previously persisted factor-evaluation results unchanged.
6. WHEN a quantile group contains future returns `R_i` with finite non-negative selected weights `w_i` and `Σw_i > 0`, THE Factor_Research_Service SHALL calculate Quantile_Return as `Σ(w_i * R_i) / Σw_i`, using `w_i = 1` for equal-weight aggregation.
7. IF a quantile group contains a negative weight, non-finite weight, missing future return, or total weight not greater than zero, THEN THE Factor_Research_Service SHALL return an undefined-quantile-return result identifying every invalid Asset input and persist no numeric Quantile_Return for that group.
8. WHEN two consecutive factor dates share `n >= 2` Assets with at least two distinct non-missing Factor_Values on each date, THE Factor_Research_Service SHALL calculate rank autocorrelation as the Pearson Information_Coefficient of the two average-tie rank vectors over exactly the shared Assets.
9. IF two consecutive factor dates share fewer than two valid Assets or either shared rank vector has zero dispersion, THEN THE Factor_Research_Service SHALL return an undefined-rank-autocorrelation result containing the shared-Asset count and invalid-vector reason.
10. WHEN two consecutive quantile portfolios have weights `w_(i,t-1)` and `w_(i,t)` over the union `U` of their Assets with absent weights treated as zero, THE Factor_Research_Service SHALL calculate one-way turnover as `0.5 * Σ_(i in U) abs(w_(i,t) - w_(i,t-1))`.
11. WHEN the selected future holding period is an integer `h` from 1 through 252 applicable valuation periods, THE Factor_Research_Service SHALL calculate each future return as `V_(i,h) / V_(i,0) - 1` from the earliest `h + 1` valid valuation endpoints whose timestamps are strictly later than the factor decision timestamp.
12. IF an Asset lacks a positive starting value, a positive ending value, or all `h + 1` required post-decision valuation endpoints, THEN THE Factor_Research_Service SHALL return one missing future-return result for the Asset identifying every missing or invalid endpoint and exclude that Asset from dependent calculations.
13. WHEN a factor evaluation completes, THE Factor_Research_Service SHALL report the factor date, decision timestamp, future holding period, aligned-Asset count, coverage ratio, missing count, Pearson and Spearman Information_Coefficient series, Information_Coefficient mean, Information_Coefficient sample standard deviation, Quantile_Return series, highest-group return minus lowest-group return, rank autocorrelation, and one-way turnover.

### Requirement 13: 组合构建与约束

**User Story:** 作为研究用户，我希望把因子信号转换为满足明确约束的多市场组合，以便获得可回测的目标权重。

#### Acceptance Criteria

1. THE Portfolio_Construction_Service SHALL require each Portfolio_Definition to contain exactly one Base_Currency, Point_In_Time_Universe version, weighting method, rebalance rule, cash policy, objective definition, immutable Portfolio_Definition version, between 0 and 256 Portfolio_Constraints, and either exactly one Benchmark version or an explicit no-Benchmark value.
2. WHEN the Portfolio_Construction_Service produces Target_Weights, THE Portfolio_Construction_Service SHALL make the sum of every Asset Target_Weight and the cash Target_Weight satisfy `abs(Σw_asset + w_cash - 1) <= 1e-12`.
3. WHEN the Portfolio_Construction_Service produces Target_Weights for the MVP, THE Portfolio_Construction_Service SHALL make every Asset Target_Weight and the cash Target_Weight fall within the inclusive range from zero through one.
4. WHEN a Portfolio_Definition specifies a maximum Asset weight `u` with `0 <= u <= 1`, THE Portfolio_Construction_Service SHALL make every Asset Target_Weight satisfy `w_i <= u + 1e-12`.
5. WHEN a Portfolio_Definition specifies a Market, currency, or industry lower bound `L` and upper bound `U` with `0 <= L <= U <= 1`, THE Portfolio_Construction_Service SHALL make the aggregate Target_Weight `g` satisfy `L - 1e-12 <= g <= U + 1e-12`.
6. WHEN a Portfolio_Definition specifies an integer maximum holding count `H` from 1 through 10000, THE Portfolio_Construction_Service SHALL produce no more than `H` Asset Target_Weights strictly greater than `1e-12`.
7. WHEN current weights `c_i` and Target_Weights `t_i` are defined over the union `U` of current and target Assets with absent weights treated as zero, THE Portfolio_Construction_Service SHALL calculate projected one-way turnover as `0.5 * (Σ_(i in U) abs(t_i - c_i) + abs(t_cash - c_cash))`.
8. WHEN a Portfolio_Definition specifies a turnover limit `T` with `0 <= T <= 1`, THE Portfolio_Construction_Service SHALL make projected one-way turnover satisfy `turnover <= T + 1e-12`.
9. WHEN multiple feasible Target_Weight sets have objective values differing by no more than `1e-12`, THE Portfolio_Construction_Service SHALL select the lexicographically greatest Target_Weight vector after ordering vector positions by ascending Canonical_Asset_ID followed by cash.
10. WHEN Target_Weights are created, THE Portfolio_Construction_Service SHALL record each input signal version, Portfolio_Definition version, constraint identifier, constraint bound, objective value, solver status, equality residual `left_side - right_side`, lower-bound residual `max(0, lower_bound - value)`, and upper-bound residual `max(0, value - upper_bound)`.
11. IF a Portfolio_Definition contains a missing required field, more than 256 Portfolio_Constraints, an invalid numeric bound, a lower bound greater than an upper bound, or an unresolved classification, THEN THE Portfolio_Construction_Service SHALL reject the complete Portfolio_Definition, identify every invalid field or constraint, produce no Target_Weights, and preserve all previously persisted target portfolios unchanged.
12. IF no Target_Weight set satisfies every Portfolio_Constraint within `1e-12`, THEN THE Portfolio_Construction_Service SHALL return an infeasible-portfolio result containing every constraint in one minimum-cardinality infeasible constraint set selected by ascending constraint identifier, produce no partial target portfolio, and preserve all previously persisted target portfolios unchanged.
13. IF a Strategy requests a negative Target_Weight, gross Asset exposure above one, borrowing, or a missing input signal version, THEN THE Portfolio_Construction_Service SHALL return an unsupported-or-invalid-portfolio result identifying every offending request, produce no Target_Weights, and preserve all previously persisted target portfolios unchanged.
14. WHEN identical input signal versions, current weights, Portfolio_Definition version, Point_In_Time_Universe version, and decision timestamp are evaluated more than once, THE Portfolio_Construction_Service SHALL reproduce the same selected Assets and produce each Target_Weight within an absolute Decimal difference of `1e-12`.

### Requirement 14: 多市场日频回测

**User Story:** 作为研究用户，我希望在保守且透明的市场假设下回测多市场组合，以便比较策略而不夸大可执行性。

#### Acceptance Criteria

1. THE Backtest_Engine SHALL accept no more than one Strategy decision timestamp per Asset per applicable market date and reject every Strategy input with a higher frequency before creating a Backtest.
2. WHEN a Strategy produces Target_Weights for a decision timestamp, THE Backtest_Engine SHALL derive those Target_Weights only from Point_In_Time_Data visible at or before the decision timestamp.
3. IF a Strategy input includes data visible after the decision timestamp, THEN THE Backtest_Engine SHALL reject the affected rebalance, identify every future-visible input version, create zero Simulated_Trades for that rebalance, and preserve positions and cash ledgers unchanged.
4. WHEN a valid Strategy decision produces Target_Weights, THE Backtest_Engine SHALL schedule each resulting Simulated_Trade for the earliest permitted Regular_Trading_Session whose start timestamp is strictly later than the decision timestamp in the Asset Market_Timezone.
5. THE Backtest_Engine SHALL use exactly the Trading_Calendar, Market_Rule_Profile, FX_Policy, FX_Rate, Corporate_Action, Transaction_Cost_Model, Data_Snapshot, and Strategy versions pinned by the Experiment_Manifest for the complete Backtest.
6. IF any required pinned version is missing or ambiguous, THEN THE Backtest_Engine SHALL reject the Backtest before the first Simulated_Trade, identify every missing or ambiguous version, and create no holdings, cash-ledger, or valuation mutation.
7. WHILE a Backtest is running, THE Backtest_Engine SHALL maintain settled cash greater than or equal to zero, unsettled cash receivables greater than or equal to zero, and every Asset quantity greater than or equal to zero after each processed event.
8. WHEN the Backtest_Engine simulates a filled trade, THE Backtest_Engine SHALL record requested quantity, valid-lot quantity, filled quantity, local execution price, Trading_Currency, Base_Currency value, FX_Rate version, gross value, each cost component, total cost, trade timestamp, source market date, Sell_Available_Date, and Settlement_Date.
9. WHEN a Transaction_Cost_Model applies to a Simulated_Trade with gross value `G`, THE Backtest_Engine SHALL calculate each cost component from the pinned model formula and effective-date parameters and make total cost equal the sum of all non-negative cost components within an absolute Decimal tolerance of `1e-12`.
10. IF Halt_Status is suspended, price-limited against the trade direction, delisted, or unknown at the scheduled Trading_Session, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, record exactly one applicable Halt_Status reason, and preserve positions and cash unchanged for that request.
11. IF a requested sell quantity exceeds the quantity whose Sell_Available_Date is no later than the simulated trade date, THEN THE Backtest_Engine SHALL assign a filled quantity of zero, identify the requested and available quantities, and preserve positions and cash unchanged for that request.
12. IF settled cash is less than a requested purchase gross value plus transaction costs, THEN THE Backtest_Engine SHALL set filled quantity to `max({k * Trading_Lot | k is a non-negative integer and k * Trading_Lot * execution_price + total_cost(k) <= settled_cash})` under the pinned Market_Rule_Profile and Transaction_Cost_Model.
13. IF the affordable purchase quantity calculated under the pinned Trading_Lot, execution price, and Transaction_Cost_Model equals zero, THEN THE Backtest_Engine SHALL assign a filled quantity of zero and preserve positions and cash unchanged for that request.
14. THE Backtest_Engine SHALL offer exactly two missing-valuation-price policies: unavailable, or the most recent valid close from no more than five applicable open market dates preceding the valuation date.
15. IF no valuation price satisfies the selected missing-valuation-price policy, THEN THE Backtest_Engine SHALL mark the affected Asset value and every dependent portfolio value unavailable for that date and preserve quantities and cash ledgers unchanged.
16. WHEN held Assets have different source market dates, THE Backtest_Engine SHALL value each Asset using the latest price and FX_Rate permitted by the pinned alignment and missing-data policies and record the source market date and FX_Rate date for each Asset value.
17. WHEN a Backtest completes, THE Backtest_Engine SHALL produce holdings, settled cash ledgers, unsettled cash ledgers, Simulated_Trades, Corporate_Action events, valuation series, transaction-cost series, unavailable-value indicators, and bias warnings linked to exactly one Experiment_Manifest.
18. IF a Strategy requests short selling, gross exposure above one, borrowing, leverage, intraday execution, a complex derivative, or a real order, THEN THE Backtest_Engine SHALL reject the complete Backtest before simulation, identify every unsupported capability, create zero Simulated_Trades, and create no holdings or cash-ledger mutation.

### Requirement 15: 风险分析

**User Story:** 作为研究用户，我希望以统一基础币种查看绝对风险、相对风险和风险贡献，以便识别组合集中度和主要风险来源。

#### Acceptance Criteria

1. WHEN the Risk_Analytics_Service forms an aligned return sample, THE Risk_Analytics_Service SHALL include exactly the periods having identical start and end timestamps and non-missing Base_Currency returns for every series required by the selected metric.
2. WHEN an aligned sample contains `n >= 2` portfolio returns `r_i` and a displayed annualization factor `A` with `0 < A <= 366`, THE Risk_Analytics_Service SHALL calculate annualized portfolio volatility as `sqrt(A * Σ(r_i - mean(r))^2 / (n - 1))`.
3. WHEN a portfolio valuation series contains `n >= 1` positive values `V_t` in ascending timestamp order, THE Risk_Analytics_Service SHALL calculate maximum drawdown as `max_t(1 - V_t / max_(s <= t)(V_s))`.
4. WHEN a Benchmark and portfolio have `n >= 2` aligned non-missing returns and displayed annualization factor `A` with `0 < A <= 366`, THE Risk_Analytics_Service SHALL calculate tracking error as `sqrt(A * Σ((r_p,i - r_b,i) - mean(r_p - r_b))^2 / (n - 1))`.
5. WHEN a Benchmark and portfolio have `n >= 2` aligned non-missing returns with positive Benchmark sample variance, THE Risk_Analytics_Service SHALL calculate portfolio beta as `Σ((r_p,i - mean(r_p)) * (r_b,i - mean(r_b))) / Σ(r_b,i - mean(r_b))^2`.
6. IF a Benchmark aligned sample has fewer than two return pairs or Benchmark sample variance equals zero, THEN THE Risk_Analytics_Service SHALL return an undefined-beta result containing the aligned-pair count and invalid-variance reason and publish no numeric beta.
7. WHEN a Risk_Model supplies a symmetric covariance matrix `Σ`, THE Risk_Analytics_Service SHALL accept the matrix as positive-semidefinite only if its smallest eigenvalue is greater than or equal to `-1e-12 * max(1, max_i(abs(Σ_(i,i))))` and every matrix row and column maps to exactly one portfolio holding.
8. IF a covariance matrix is non-square, non-symmetric within an absolute Decimal tolerance of `1e-12`, misaligned to holdings, contains a non-finite value, violates the positive-semidefinite tolerance, or produces portfolio variance `w^TΣw <= 0`, THEN THE Risk_Analytics_Service SHALL mark every covariance-dependent metric unavailable, identify every failed condition, and preserve all independently calculated risk metrics.
9. WHEN an accepted covariance matrix produces positive portfolio variance `v = w^TΣw`, THE Risk_Analytics_Service SHALL calculate each positive holding's marginal variance contribution as `(Σw)_i`, component variance contribution as `w_i * (Σw)_i`, and component volatility contribution as `w_i * (Σw)_i / sqrt(v)`.
10. WHEN component variance contributions are calculated, THE Risk_Analytics_Service SHALL make `abs(Σ_i(w_i * (Σw)_i) - w^TΣw) <= 1e-10 * max(1, abs(w^TΣw))`.
11. WHEN positive Base_Currency Asset market values `v_i` have total `V = Σv_i > 0`, THE Risk_Analytics_Service SHALL calculate each Asset weight as `v_i / V`, single-Asset concentration as the largest Asset weight, top-five-Asset concentration as the sum of the largest `min(5, n)` Asset weights, and each Market, industry, and currency concentration as the sum of Asset weights in that classification group.
12. IF a required price, FX_Rate, Benchmark return, classification, covariance value, or Base_Currency market value is missing or invalid, THEN THE Risk_Analytics_Service SHALL mark each dependent metric unavailable, identify every missing or invalid input by category and affected period or Asset, publish no numeric value for the dependent metric, and preserve all independently calculated metrics.
13. WHEN a risk report is generated, THE Risk_Analytics_Service SHALL include the Data_Snapshot identifier, Risk_Model version, Base_Currency, aligned date range, aligned sample count for each metric, return convention, annualization factor, covariance tolerance, missing-data policy, Data_Quality_Status summary, and every unavailable-metric reason.

### Requirement 16: 绩效计算与归因

**User Story:** 作为研究用户，我希望解释组合收益来自哪些资产、市场、行业和币种，以便区分信号效果与外汇或配置效果。

#### Acceptance Criteria

1. WHEN the Performance_Attribution_Service calculates a periodic portfolio return, THE Performance_Attribution_Service SHALL calculate `R = (E - B - sum(F_i)) / (B + sum(w_i * F_i))`, where `B` is beginning Base_Currency value, `E` is ending Base_Currency value, `F_i` is the signed Base_Currency external cash flow at time `i`, and `w_i` is the fraction of the period remaining after time `i` in the inclusive range from zero through one.
2. IF `B + sum(w_i * F_i)` is zero or any required value or cash flow is unavailable, THEN THE Performance_Attribution_Service SHALL mark the periodic portfolio return unavailable, identify every invalid input, and publish no dependent attribution result for that period.
3. WHEN Asset-level beginning weights and returns are available, THE Performance_Attribution_Service SHALL calculate each Asset contribution as `C_a = W_a * R_a`, where `W_a` is the Asset beginning-period Base_Currency weight and `R_a` is the Asset Base_Currency return.
4. WHEN transaction costs occur during a period, THE Performance_Attribution_Service SHALL calculate transaction-cost drag as `C_cost = -TC / D`, where `TC` is the non-negative Base_Currency transaction cost and `D = B + sum(w_i * F_i)` is the positive return denominator for that period.
5. WHEN cash has a beginning-period weight, THE Performance_Attribution_Service SHALL calculate cash contribution as `C_cash = W_cash * R_cash`, where `W_cash` is the beginning-period cash weight and `R_cash` is the cash return for the period.
6. WHEN Asset, cash, and transaction-cost contributions are calculated, THE Performance_Attribution_Service SHALL calculate residual as `Residual = R - sum(C_a) - C_cash - C_cost` and make the absolute residual no greater than `1e-10`.
7. WHEN a Benchmark is supplied for an aligned period, THE Performance_Attribution_Service SHALL calculate active return as `R_active = R_portfolio - R_benchmark`.
8. WHEN Market or industry attribution inputs are available, THE Performance_Attribution_Service SHALL calculate each Brinson-Fachler allocation effect as `A_j = (W_Pj - W_Bj) * (R_Bj - R_B)`, where `j` is the classification group, `W_Pj` and `W_Bj` are portfolio and Benchmark beginning weights, `R_Bj` is the Benchmark group return, and `R_B` is the Benchmark total return.
9. WHEN Market or industry attribution inputs are available, THE Performance_Attribution_Service SHALL calculate each Brinson-Fachler selection effect as `S_j = W_Bj * (R_Pj - R_Bj)`, where `R_Pj` is the portfolio group return and the other terms have the meanings defined by the Brinson-Fachler allocation criterion.
10. WHEN Market or industry attribution inputs are available, THE Performance_Attribution_Service SHALL calculate each Brinson-Fachler interaction effect as `I_j = (W_Pj - W_Bj) * (R_Pj - R_Bj)`.
11. WHEN Brinson-Fachler effects are calculated, THE Performance_Attribution_Service SHALL calculate attribution residual as `Residual_BF = R_active - sum(A_j + S_j + I_j)` and make the absolute attribution residual no greater than `1e-10`.
12. WHEN an Asset Trading_Currency differs from Base_Currency, THE Performance_Attribution_Service SHALL calculate `R_base = (1 + R_local) * (1 + R_FX) - 1`, where `R_local` is the local-asset return and `R_FX` is the Base_Currency return of one unit of Trading_Currency.
13. WHEN an Asset Trading_Currency differs from Base_Currency, THE Performance_Attribution_Service SHALL calculate local-asset effect as `C_local = W_a * R_local` and FX effect as `C_FX = W_a * (1 + R_local) * R_FX`.
14. WHEN the Performance_Attribution_Service geometrically links periodic contributions, THE Performance_Attribution_Service SHALL calculate each linked contribution recursively as `L_i,t = L_i,t-1 * (1 + R_t) + C_i,t`, with `L_i,0 = 0`, and make `sum(L_i,T)` equal `product(1 + R_t) - 1` within an absolute tolerance of `1e-10`.
15. IF any required Benchmark weight, classification, FX_Rate, beginning weight, return, external cash flow, or transaction cost is unavailable, non-finite, or not aligned to the attribution period, THEN THE Performance_Attribution_Service SHALL mark every dependent attribution component unavailable, identify every invalid input category, and preserve every independent component unchanged.
16. WHEN an attribution report is generated, THE Performance_Attribution_Service SHALL include the attribution method, return formula, Base_Currency, Benchmark version, classification versions, FX_Policy, cost treatment, geometric linking formula, residual, Data_Snapshot, and Data_Quality_Status summary.

### Requirement 17: 实验可复现性与比较

**User Story:** 作为研究用户，我希望每次因子、组合、回测、风险和归因实验都能被重放和比较，以便解释结果差异。

#### Acceptance Criteria

1. WHEN the Experiment_Runner creates a Research_Run, THE Experiment_Runner SHALL persist exactly one immutable Experiment_Manifest before publishing any result for that Research_Run.
2. THE Experiment_Manifest SHALL contain the Research_Run identifier, Data_Snapshot, Point_In_Time_Universe version, date range, Base_Currency, FX_Policy, Data_Provider versions, Trading_Calendar versions, Market_Rule_Profile versions, Adjustment_Mode, data-quality rule versions, Factor_Definition versions, Portfolio_Definition version, Strategy version, Transaction_Cost_Model version, Risk_Model version, parameters, random seed, code version, and dependency environment version.
3. THE Experiment_Runner SHALL assign each Data_Snapshot an immutable identifier derived from the complete ordered content and versions of every referenced dataset.
4. WHEN the Experiment_Runner creates an Experiment_Manifest, THE Experiment_Runner SHALL pin exactly one immutable version of every referenced data, Provider_Asset_Mapping, Trading_Calendar, Valuation_Calendar, Market_Rule_Profile, FX_Rate, Corporate_Action, Adjustment_Factor, quality rule, Factor_Definition, Point_In_Time_Universe, Portfolio_Definition, Strategy, Transaction_Cost_Model, Risk_Model, code, and dependency environment artifact.
5. IF any required Experiment_Manifest field or referenced artifact version is absent or ambiguous, THEN THE Experiment_Runner SHALL reject Research_Run creation, publish no result, identify every absent or ambiguous item, and preserve all existing Research_Runs unchanged.
6. WHEN the Research_User requests replay, THE Experiment_Runner SHALL use exactly the artifact versions, parameters, date range, Base_Currency, FX_Policy, and random seed recorded in the selected Experiment_Manifest.
7. IF any artifact pinned by the selected Experiment_Manifest is unavailable or fails content-identifier verification, THEN THE Experiment_Runner SHALL publish no replay result, identify every unavailable or mismatched artifact, and preserve the original Research_Run and published results unchanged.
8. WHEN a deterministic Research_Run is replayed with every pinned artifact available, THE Experiment_Runner SHALL reproduce every discrete output exactly.
9. WHEN a deterministic Research_Run is replayed with every pinned artifact available, THE Experiment_Runner SHALL reproduce each finite numeric output within `abs(replayed - original) <= 1e-10 * max(1, abs(original))`.
10. WHEN two Research_Runs are compared, THE Experiment_Runner SHALL report every Experiment_Manifest field whose values differ and the value from each Research_Run.
11. WHEN two Research_Runs are compared, THE Experiment_Runner SHALL report each aligned finite numeric result difference as absolute difference and relative difference, using zero relative difference for two zero values and unavailable relative difference when exactly one value is zero.
12. WHEN two Research_Runs are compared, THE Experiment_Runner SHALL classify aligned finite numeric results as equivalent only when `abs(value_1 - value_2) <= 1e-10 * max(1, abs(value_1), abs(value_2))`.
13. WHEN a Research_Run uses randomness, THE Experiment_Runner SHALL record exactly one explicit random seed before execution and use the recorded seed during every replay.
14. IF a Research_Run uses randomness without an explicit random seed, THEN THE Experiment_Runner SHALL reject the Research_Run, publish no result, and preserve all existing Research_Runs unchanged.
15. THE Experiment_Runner SHALL preserve every persisted Experiment_Manifest, Data_Snapshot identifier, and published result without modification or deletion.

### Requirement 18: 研究接口与结果查询

**User Story:** 作为研究用户，我希望通过页面、命令行和本地脚本查询统一数据并运行实验，以便支持交互分析和可编程研究。

#### Acceptance Criteria

1. THE Research_Interface SHALL provide the same read-only query and Research_Run submission capabilities through a local page, a command-line interface, and a local Python script interface.
2. THE Research_Interface SHALL provide read-only queries for Asset_Master, Daily_Bar, Fund_NAV, Fundamental_Fact, Corporate_Action, Trading_Calendar, Market_Rule_Profile, FX_Rate, Factor_Value, Data_Quality_Status, Data_Snapshot, and research results.
3. WHEN the Research_Interface returns a query result, THE Research_Interface SHALL include the selected Data_Snapshot identifier, query parameters, matching-record count, returned-record count, applied-filter count, and additional-results indicator.
4. THE Research_Interface SHALL accept from zero through 20 filters in one query.
5. IF a query specifies more than 20 filters, THEN THE Research_Interface SHALL reject the complete query, identify 20 as the maximum, return zero records, and preserve the selected Data_Snapshot and all persisted records unchanged.
6. THE Research_Interface SHALL return at most 10000 records from one query.
7. WHEN a query has more than 10000 matching records, THE Research_Interface SHALL return exactly the first 10000 records ordered lexicographically by applicable Canonical_Asset_ID, observation date or timestamp, and immutable version identifier, and set the additional-results indicator to true.
8. WHEN a query has no more than 10000 matching records, THE Research_Interface SHALL return every matching record ordered lexicographically by applicable Canonical_Asset_ID, observation date or timestamp, and immutable version identifier, and set the additional-results indicator to false.
9. WHEN a returned record lacks one of the stable-order attributes, THE Research_Interface SHALL place the record before records with a value for that attribute and preserve ascending order for every remaining attribute.
10. WHEN the Research_User submits a Research_Run, THE Research_Interface SHALL require an explicit Data_Snapshot identifier, inclusive start date, inclusive end date, Base_Currency, and every referenced research definition version.
11. IF a Research_Run request omits or ambiguously identifies a required version, THEN THE Research_Interface SHALL reject the complete request, identify every omitted or ambiguous version, create no Research_Run, and preserve all persisted records unchanged.
12. IF a Research_Run start date is later than the end date, THEN THE Research_Interface SHALL reject the complete request, identify the invalid date range, create no Research_Run, and preserve all persisted records unchanged.
13. WHEN the Research_Interface displays a dataset or result, THE Research_Interface SHALL display Data_Provenance, Data_Quality_Status, currency, date semantics, Data_Snapshot identifier, and every applicable bias warning.
14. WHEN the Research_Interface executes a read-only query, THE Research_Interface SHALL preserve the selected Data_Snapshot and every persisted record unchanged.
15. THE Research_Interface SHALL expose zero arbitrary write-capable database connections, unrestricted filesystem locations, or unrestricted Data_Provider requests to local scripts.
16. IF a query references an unavailable Data_Snapshot or unsupported filter, THEN THE Research_Interface SHALL reject the complete query, identify every unavailable or unsupported input, return zero records, and preserve all persisted records unchanged.

### Requirement 19: 凭据、网络与敏感信息

**User Story:** 作为研究用户，我希望数据供应商凭据和出站访问受到限制，以便降低密钥泄露和未授权传输风险。

#### Acceptance Criteria

1. THE Credential_Manager SHALL store every Credential outside the Research_Workspace and outside every version-controlled project location.
2. THE Credential_Manager SHALL permit Credential content access only to processes executing under the Research_User operating-system identity.
3. IF a process executing under a different operating-system identity requests Credential content, THEN THE Credential_Manager SHALL deny the request, return no Credential content, and preserve every Credential unchanged.
4. WHEN the Multi_Market_Quant_Platform prepares display, log, export, report, error, or request-metadata content, THE Credential_Manager SHALL replace every complete detected Credential or configured recoverable Credential representation with `[REDACTED]` before the content becomes observable or persistent.
5. IF Secret_Redaction cannot complete or cannot determine whether prepared content contains Credential material, THEN THE Credential_Manager SHALL suppress the complete content, persist zero bytes of the content, and preserve every Credential unchanged.
6. IF a required Credential is absent or inaccessible, THEN THE Provider_Adapter SHALL send zero Data_Provider requests, return a credential-unavailable indication containing no Credential content, and preserve every persisted dataset unchanged.
7. WHEN the Research_User configures a Data_Provider endpoint, THE Multi_Market_Quant_Platform SHALL accept only an HTTPS origin with an explicit non-empty allowed path scope.
8. IF a configured Data_Provider endpoint uses a scheme other than HTTPS or omits the allowed path scope, THEN THE Multi_Market_Quant_Platform SHALL reject the endpoint, send zero network bytes to the endpoint, and preserve the prior endpoint configuration unchanged.
9. WHEN the Provider_Adapter prepares an outbound request, THE Multi_Market_Quant_Platform SHALL permit transmission only when the target HTTPS origin exactly equals the configured Data_Provider origin and the normalized target path is within the configured allowed path scope.
10. IF an outbound target or any redirect target differs from the configured HTTPS origin or falls outside the configured allowed path scope, THEN THE Multi_Market_Quant_Platform SHALL block the connection before transmitting Credential content, request metadata, or Data_Provider data and preserve persisted data unchanged.
11. WHEN the Research_User deletes a Provider_Adapter configuration, THE Multi_Market_Quant_Platform SHALL present every associated Credential as an independently selectable deletion option before deleting any Credential.
12. WHEN the Research_User confirms Credential deletion selections, THE Credential_Manager SHALL delete exactly the selected Credentials and preserve every unselected Credential unchanged.
13. IF deletion of any selected Credential fails, THEN THE Credential_Manager SHALL preserve every Credential selected in that deletion operation and identify each failed deletion without exposing Credential content.
14. THE Multi_Market_Quant_Platform SHALL transmit zero telemetry and zero research data to non-provider external services unless the Research_User explicitly enables a named destination and data category.
15. IF Secret_Redaction detects Credential material in an outbound non-provider transmission, THEN THE Multi_Market_Quant_Platform SHALL block the complete transmission, transmit zero bytes, and preserve the source content unchanged.

### Requirement 20: 本地运维、备份与恢复

**User Story:** 作为研究用户，我希望验证平台状态并备份和恢复完整研究资产，以便在个人设备上维护独立量化项目。

#### Acceptance Criteria

1. THE Multi_Market_Quant_Platform SHALL report platform version, enabled Provider_Adapter versions, Adapter_Contract versions, schema version, compatible restore schema versions, available storage bytes as a non-negative integer, and latest successful ingestion time as named status fields.
2. WHEN no ingestion has succeeded, THE Multi_Market_Quant_Platform SHALL report an explicit no-success state for latest successful ingestion time.
3. WHEN the Research_User requests a backup, THE Multi_Market_Quant_Platform SHALL include platform configuration excluding plaintext Credentials, every Asset_Master version, every Provider_Asset_Mapping, every Trading_Calendar, every Valuation_Calendar, every Market_Rule_Profile, every permitted retained dataset and Data_Version, every Data_Quality_Report, every Data_Snapshot, every Factor_Definition, every Point_In_Time_Universe, every Portfolio_Definition, every Experiment_Manifest, and every published research result selected for the backup.
4. WHEN the Multi_Market_Quant_Platform creates a backup, THE Multi_Market_Quant_Platform SHALL generate a Backup_Manifest containing schema version, dataset identity, non-negative record count, content checksum, immutable version identifiers, and referenced object list for every included dataset.
5. WHEN backup data writing completes, THE Multi_Market_Quant_Platform SHALL verify every included dataset against the corresponding Backup_Manifest record count and content checksum before marking the backup restorable.
6. IF any Backup_Manifest record count or content checksum verification fails, THEN THE Multi_Market_Quant_Platform SHALL mark the backup not restorable, identify every failed dataset, and preserve every pre-existing backup unchanged.
7. IF available storage bytes are less than estimated ingestion bytes, THEN THE Data_Ingestion_Service SHALL stop before sending a Data_Provider request, report both values as non-negative integers, and preserve every persisted dataset unchanged.
8. WHEN a schema migration is required, THE Multi_Market_Quant_Platform SHALL create and verify a restorable backup of the complete pre-migration state before changing the schema or stored data.
9. IF pre-migration backup creation or verification fails, THEN THE Multi_Market_Quant_Platform SHALL perform no migration and preserve the complete pre-migration schema and stored data unchanged.
10. WHEN the Research_User requests restoration of a compatible verified backup, THE Multi_Market_Quant_Platform SHALL restore all included datasets as one atomic restoration operation.
11. WHEN an atomic restoration succeeds, THE Multi_Market_Quant_Platform SHALL report the post-restore record count and content checksum for every restored dataset.
12. IF backup compatibility, restoration, record-count verification, or checksum verification fails, THEN THE Multi_Market_Quant_Platform SHALL restore the complete pre-restoration state, publish no partial restored state, and identify every failed condition.
13. WHEN a backup includes Credential material, THE Multi_Market_Quant_Platform SHALL mark the backup complete only after authenticated encryption of all Credential material succeeds and the encrypted backup passes Backup_Manifest verification.
14. IF encryption or verification of a backup containing Credential material fails, THEN THE Multi_Market_Quant_Platform SHALL delete every artifact created by the failed backup operation, mark the backup incomplete, and preserve every pre-existing backup unchanged.
15. IF deletion of any artifact from a failed sensitive backup operation fails, THEN THE Multi_Market_Quant_Platform SHALL mark every remaining artifact not restorable, identify each undeleted artifact without exposing Credential content, and preserve every pre-existing backup unchanged.

