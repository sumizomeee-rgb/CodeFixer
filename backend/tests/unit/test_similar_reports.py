from codefixer.application.services.similar_reports import title_similarity


def test_same_feature_titles_match_without_version_tags_driving_similarity() -> None:
    score, feature = title_similarity(
        "【v4.8、trunk】【一键养成-武器养成】养成总览界面，武器谐振后品质底未变化",
        "【v4.8、trunk】【一键养成-目标设定】选择另一个目标时没有二次确认框",
    )

    assert score >= 0.70
    assert feature == "一键养成"


def test_version_only_match_does_not_share_report() -> None:
    score, feature = title_similarity(
        "【v4.8、trunk】【一键养成-武器养成】品质底未变化",
        "【v4.8、trunk】【公会战】排行榜显示错误",
    )

    assert score < 0.62
    assert feature is None


def test_product_release_tag_does_not_make_unrelated_modules_similar() -> None:
    score, feature = title_similarity(
        "【战双兄弟2.0】【v4.8、trunk】【一键养成】品质底未变化",
        "【战双兄弟2.0】【v4.8、trunk】【公会战】排行榜显示错误",
    )

    assert score < 0.62
    assert feature is None
