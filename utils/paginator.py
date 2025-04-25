from discord.ui import View, Button
import discord


class PaginatorView(View):
    def __init__(
        self,
        pages: list[discord.Embed],
        author: discord.User,
        *,
        loop: bool = False,
        timeout: int = 60,
    ):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.index = 0
        self.loop = loop
        self.message = None
        self.author = author

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass

    async def send(self, ctx):
        self.update_buttons()
        self.message = await ctx.send(embed=self.pages[self.index], view=self)

    def update_buttons(self):
        self.children[0].disabled = len(self.pages) <= 1 or (
            self.index == 0 and not self.loop
        )
        self.children[1].disabled = len(self.pages) <= 1 or (
            self.index == len(self.pages) - 1 and not self.loop
        )

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )
            return

        if self.index > 0:
            self.index -= 1
        elif self.loop:
            self.index = len(self.pages) - 1
        else:
            return await interaction.response.defer()
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: Button):
        if interaction.user != self.author:
            await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )
            return

        if self.index < len(self.pages) - 1:
            self.index += 1
        elif self.loop:
            self.index = 0
        else:
            return await interaction.response.defer()
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)
