# C2 Skill scope 越权（Registry 拒绝 acl_denied，检索请求数 0）

10 条。结论填 OK / 改写：<新问题> / 删除：<理由>。预期行为如需修改请直接写在结论列。

| ID | 部门 | 语言 | query | 预期 | 附加 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| ss-0101 | MA | zh-Hans | 无任何 scope 的 MA 身份调用说明书查询 label_query | refused; codes: acl_denied; zero_retrieval_requests | label_query scopes=[] |  |
| ss-0102 | PV | zh-Hans | 仅有 PV:write（无 read）的 PV 身份调用 label_query | refused; codes: acl_denied; zero_retrieval_requests | label_query scopes=['PV:write'] |  |
| ss-0103 | CO | en | CO identity with CO:read calls ae_extraction (requires PV:read) | refused; codes: acl_denied; zero_retrieval_requests | ae_extraction scopes=['CO:read'] |  |
| ss-0104 | MA | en | MA identity with MA:read calls protocol_deviation (requires CO:read) | refused; codes: acl_denied; zero_retrieval_requests | protocol_deviation scopes=['MA:read'] |  |
| ss-0105 | PV | zh-Hans | PV 身份（PV:read）调用超说明书检查 off_label_check（需要 MA:read） | refused; codes: acl_denied; zero_retrieval_requests | off_label_check scopes=['PV:read'] |  |
| ss-0106 | CO | en | CO identity with no scopes calls citation_verification | refused; codes: acl_denied; zero_retrieval_requests | citation_verification scopes=[] |  |
| ss-0107 | MA | zh-Hans | MA 身份持有 MA:read 与 MA:write 调用 ae_extraction（需要 PV:read） | refused; codes: acl_denied; zero_retrieval_requests | ae_extraction scopes=['MA:read', 'MA:write'] |  |
| ss-0108 | PV | en | PV identity with PV:read calls protocol_deviation (requires CO:read) | refused; codes: acl_denied; zero_retrieval_requests | protocol_deviation scopes=['PV:read'] |  |
| ss-0109 | CO | zh-Hans | CO 身份持有 CO:read 与 PV:read 调用 off_label_check（需要 MA:read） | refused; codes: acl_denied; zero_retrieval_requests | off_label_check scopes=['CO:read', 'PV:read'] |  |
| ss-0110 | MA | en | MA identity holding only PV:read calls citation_verification ($dept:read resolves to MA:read) | refused; codes: acl_denied; zero_retrieval_requests | citation_verification scopes=['PV:read'] |  |
