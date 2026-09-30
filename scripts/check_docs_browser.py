"""Optional browser QA for the two documentation portals (Playwright + Chrome)."""
import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8088/PreparationPalAI/')
    parser.add_argument('--screenshots', type=Path, default=Path('/tmp/preparationpal-docs'))
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=os.environ.get('CHECK_BROWSER', 'chrome'))
        page = browser.new_page(viewport=dict(width=1440, height=1000))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.base_url)
        page.evaluate('document.fonts.ready')
        assert page.evaluate('document.fonts.check(\'700 20px "Manrope"\')')
        assert page.evaluate('document.fonts.check(\'400 16px "Source Sans 3"\')')
        expect(page.locator('h1')).to_have_count(1)
        expect(page.get_by_role('heading', level=1)).to_contain_text('Make your next')
        page.screenshot(path=str(args.screenshots / 'product-desktop.png'), full_page=True)
        page.get_by_title('Switch to dark mode', exact=True).click()
        expect(page.locator('body')).to_have_attribute('data-md-color-scheme', 'slate')
        page.screenshot(path=str(args.screenshots / 'product-dark.png'), full_page=True)
        page.get_by_title('Switch to light mode', exact=True).click()
        search = page.get_by_role('textbox', name='Search', exact=True)
        search.type('weak areas')
        expect(page.locator('.md-search-result__item').first).to_be_visible()
        search.fill('')
        search.type('SQLITE')
        expect(page.locator('.md-search-result__meta')).to_contain_text('No matching documents')
        page.keyboard.press('Escape')
        page.get_by_role('link', name='Start your first session').click()
        expect(page.get_by_role('heading', level=1)).to_contain_text('Your first study session')
        for width in (320, 375, 768):
            page.set_viewport_size(dict(width=width, height=900))
            page.goto(args.base_url)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            page.screenshot(path=str(args.screenshots / f'product-{width}.png'), full_page=True)
        page.locator('label.md-header__button[for="__drawer"]').click()
        expect(page.locator('#__drawer')).to_be_checked()
        overlay = page.locator('label.md-overlay[for="__drawer"]')
        bounds = overlay.bounding_box()
        overlay.click(position=dict(x=bounds['width'] - 4, y=200))
        page.set_viewport_size(dict(width=1440, height=1000))
        page.goto(args.base_url + 'contribute/')
        expect(page.get_by_role('heading', level=1)).to_contain_text('Make studying better, together.')
        page.screenshot(path=str(args.screenshots / 'contributors-desktop.png'), full_page=True)
        search = page.get_by_role('textbox', name='Search', exact=True)
        search.type('AUTH_TOKENS')
        expect(page.locator('.md-search-result__item').first).to_be_visible()
        page.keyboard.press('Escape')
        page.get_by_role('link', name='Back to the user guide').click()
        expect(page.get_by_role('heading', level=1)).to_contain_text('Make your next')
        assert not errors, errors
        browser.close()
    print(f'Documentation search, themes, navigation and responsive checks passed. Screenshots: {args.screenshots}')


if __name__ == '__main__':
    main()
